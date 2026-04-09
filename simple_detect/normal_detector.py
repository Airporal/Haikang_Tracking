import cv2
import numpy as np
from scipy.linalg import lstsq
from detecter_help import *
import os
import pandas as pd
from scipy.optimize import least_squares

import numpy as np
import cv2
def residuals(params, src_pts, tgt_pts):
    """ 计算残差 """
    # 构造4x4仿射矩阵
    affine = np.array([
        [params[0], params[1], params[2], params[3]],
        [params[4], params[5], params[6], params[7]],
        [params[8], params[9], params[10], params[11]],
        [0.0, 0.0, 0.0, 1.0]
    ])
    # 转换源点为齐次坐标并转置为(4, N)
    src_hom = np.hstack((src_pts, np.ones((src_pts.shape[0], 1)))).T
    # 应用仿射变换
    pred_hom = affine @ src_hom  # 结果形状为(4, N)
    # 转换为Nx3的矩阵
    pred_pts = pred_hom[:3, :].T
    # 计算残差并展平
    return (pred_pts - tgt_pts).ravel()
class NormalDetector:
    def __init__(self, row, col):
        """
            col : 列数, 向右为正,真实x距离与col号关系, x = (col-1)*43.301/2,单位mm
            row : 行数, 向上为正,真实y距离与row号关系, y = (row-1)*25.0/2, 单位mm
        """
        # 环境参数
        self.frame = None
        self.draw_flag = True  # 绘图
        self.Locator_initFlag = False # 当有第一个外参矩阵后标记为True
        self.now_positions = None # 当前位置 4x3
        self.threshold = 200  # 跟随阈值,像素偏差小于此值则不调整
        self.start_threshold = 300 # 启动跟踪阈值，像素偏差大于此阈值，则开启跟踪
        self.stop_threshold = 100 # 停止跟踪阈值，像素偏差小于此阈值，则不再跟踪
        self.track = False
        self.center = None # 中心位置
        
        # 相机内参
        current_dir = os.path.dirname(__file__)
        project_dir = os.path.dirname(current_dir)
        INTRINSIC = os.path.join(project_dir, 'config','camera_calibration.npz')
        camera_data = np.load(INTRINSIC)
        self.camera_matrix = camera_data['camera_matrix']
        self.dist_coeffs = camera_data['dist_coeffs']
        self.extrinsic = None # 外参矩阵
        self.inv_extrinsic = None # 逆外参矩阵
        self.frame_shape = None # 图像尺寸
        
        # aruco检测参数
        self.marker_length = 0.035 # aruco标记边长 in meters 大的是0.037 小的是0.035
        self.update_exterinsic_threshold = 3 
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.parameters.adaptiveThreshWinSizeMin = 3
        self.parameters.adaptiveThreshWinSizeMax = 35   # 原来23，可以再放大一些
        self.parameters.adaptiveThreshWinSizeStep = 2  # 原来10，改小更精细
        self.parameters.minMarkerPerimeterRate = 0.01  # 默认0.03
        self.parameters.minCornerDistanceRate = 0.01
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        
        # 初始化机器人的位置，腿的分布是4-3-2-1 对应aruco 3-2-1-0
        self._leg_quad = np.array([[1, -1], [-1, -1], [-1, 1], [1, 1]])
        self._leg_dev  = np.array([194.85, 62.5])
        self.center_row = row
        self.center_col = col
        self._caculate_legs_position(row, col, init_flag=True) 
    
    # -------------------- 腿和中心的转换 -------------------- #
    def _caculate_legs_position(self, row = 61, col=77, init_flag=False):
        """
            根据行和列计算机器人四个足的位置,4x3
        """
        # col 对应计算x坐标，row对应计算y坐标
        
        robot_c = np.array([(col-1)*43.301/2, (row-1)*25.0/2])
        # print(f"row:{row} , col:{col} , robot_c:{robot_c}")
        # 计算机器人四个足端的位置 4x3
        real_positions = robot_c + self._leg_quad * self._leg_dev
        real_positions = np.hstack((np.array([3,2,1,0]).reshape(-1,1),real_positions)) 
        if init_flag:
            self.init_positions = real_positions
            self.now_positions = real_positions
            print(f"👍 Init robot positions Success:\n{self.init_positions,robot_c}!")
        return real_positions 
    
    def _calculate_center_position(self, leg_positions, threshold=50.0):
        """
        逆向计算: 已知四足位置 -> 估计中心位置
        :param leg_positions: (4x3) numpy array
        :param threshold: 距离阈值，用于剔除偏差大的估计
        :return: 最终估计的中心坐标 (x, y)
        """
        # 逐腿反推中心
        centers = []
        leg_positions,idxs = self.get_useful(leg_positions) # Mx3
        leg_positions = leg_positions[:, 1:] # Mx2
        for i,idx in enumerate(idxs):
            est_center = leg_positions[i] - self._leg_quad[idx] * self._leg_dev
            centers.append(est_center)
        centers = np.array(centers)
        # 计算均值作为参考中心
        mean_center = np.mean(centers, axis=0)
        # 计算每个估计与均值的距离
        dists = np.linalg.norm(centers - mean_center, axis=1)

        # 只保留偏差小于阈值的估计
        valid_centers = centers[dists < threshold]

        if len(valid_centers) == 0:
            print("⚠️ 所有估计都被剔除了，返回均值结果")
            return mean_center, len(centers)

        # 返回鲁棒的中心 (有效估计的平均值)
        return np.mean(valid_centers, axis=0), len(centers) 
    
    # -------------------- aruco检测模块 -------------------- #
    # @stopwatch
    def detect_markers(self, image_file):
        """
            耗时90ms
            检测aruco码并返回aruco码的3D坐标和姿态估计
            确保markers的顺序与初始标定一致
            update 表示保存当前检测的锚点坐标
            marker_list: 4x4 3D坐标 idx,x,y,z 丢失为-1
        """
        # 如果传入地址，则读取, 如果是图片则直接赋值
        if isinstance(image_file, str):
            image = cv2.imread(image_file) # 0.02
        else:
            image = image_file
        # 图像增强
        show_img = image.copy()
        image = self._enhance_img(image) # 0.02

        # 检测aruco码 
        corners, ids, _ = self.detector.detectMarkers(image) # 0.036
        # 下面的过程耗时小于9ms
        if ids is not None:
            # 角点亚像素增强
            corners = self._refine_corner(corners,image)
            # 从大到小排列3-2-1-0
            sorted_indices = np.argsort(ids.flatten())[::-1]
            corners_sorted = [corners[i] for i in sorted_indices]
            self.corners = corners_sorted
            ids_sorted = ids[sorted_indices]
            # aruco码姿态估计
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners_sorted, self.marker_length, self.camera_matrix, self.dist_coeffs)
            # 计算并储存相对锚点坐标：idx->xyz
            anchor = np.array([0, 0, 0]) # 设置锚点3D坐标
            marker_dict = {}
            marker_list = []
            for i, idx in enumerate(ids_sorted):
                marker_list.append(tvecs[i].reshape(3) - anchor)
                marker_dict[idx[0]] = marker_list[-1]
            marker_list = np.array(marker_list)
            if self.draw_flag:
                # print(f"❤️ids_sorted: {ids_sorted}")
                # show_3D(self.markers)
                # self._show_debug(marker_dict)
                # 此处耗时8ms
                cv2.aruco.drawDetectedMarkers(show_img, corners_sorted, ids_sorted)
                # 根据aruco码的位姿标注出对应的xyz轴
                for r, t in zip(rvecs, tvecs):
                    cv2.drawFrameAxes(show_img, self.camera_matrix,
                                    self.dist_coeffs, r, t, 0.02, 2)
                # cv2.putText(show_img, f"frame freq:{self.freq}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                # self._show_markers(show_img, corners_sorted, ids_sorted, rvecs, tvecs)
                
            marker_list = np.array([[k, *v] for k, v in zip(marker_dict.keys(), marker_list)])
            
            ALL = np.zeros((4, marker_list.shape[1]), dtype=marker_list.dtype)
            idx = []
            for row_idx, marker_id in enumerate([3,2,1,0]):
                if marker_id in ids_sorted:
                # 找到对应 idx 中的行
                    mapped_row = marker_list[np.where(ids_sorted == marker_id)[0][0]]
                    ALL[row_idx] = mapped_row
                    idx.append(row_idx)
                else:
                    # 缺失坐标，保持为-1
                    ALL[row_idx] = -1
            marker_list = ALL
            pix_points = []
            for i, aruco_id in enumerate(idx):
                corner = corners[i][0]  # (4,2)
                pix_center = corner.mean(axis=0)  # 足端像素中心
                pix_points.append([aruco_id, pix_center[0], pix_center[1]])
            pix_points = np.array(pix_points)
            self.center = np.mean(pix_points[:,1:],axis=0)
            # print(f"center_mean: \n{idx,center_mean}")
            # print(f"marker_list: {marker_list}")
            return marker_list, marker_dict, show_img
        else:
            # 没有检测的aruco码,返回None
            print("None aruco")
            return None, None, show_img
        
    # -------------------- 外参校准模块 -------------------- #
    def init_extrinsic(self, frame):
        """
            初始化外参矩阵
        """
        # 初始化校准外参矩阵，根据初始测量位置计算外参矩阵
        self.frame_shape = frame.shape
        # init_marker_list: 4x4 3D坐标 idx,x,y,z 丢失为-1
        init_marker_list, init_marker_dict, show_img = self.detect_markers(image_file = frame)
        if init_marker_list is not None:
            flag = self.update_extrinsic_from_lstsq(markers=init_marker_list,real_positions=self.init_positions)
            if flag is not None:
                print("👍 初始外参矩阵计算成功！")
            self.Locator_initFlag = True
        else:
            print("❌ 初始外参矩阵计算失败，请检查初始位置")
        return init_marker_list, init_marker_dict, show_img
    
    # @stopwatch
    def update_extrinsic_from_lstsq(self,markers=None, real_positions=None):
        """
            耗时 0.001189
            markers: 4x4 3D坐标 idx,x,y,z
            real_positions: 4x3 真实位置 idx,x,y
            丢失的位置用-1表示
        """
        # 过滤掉丢失的坐标
        # print(f"markers: {markers}")
        # print(f"real_positions: {real_positions}")
        mask = (markers[:, 0] != -1) & (real_positions[:, 0] != -1) # m>2
        coords_A = markers[mask, 1:]  # mx3
        idx = markers[mask, 0].astype(int) # mx1, aruco标记的id
        coords_B = real_positions[mask, 1:]  # mx2
        
        points_num = len(coords_A)
        if points_num < self.update_exterinsic_threshold:
            print(f"❌ Not enough markers ({points_num}), "
                  f"need at least {self.update_exterinsic_threshold}")
            return None
        
        # 构造 A' (加齐次列1)
        A_aug = np.hstack([coords_A, np.ones((coords_A.shape[0], 1))])  # m×4
        # 构造 B' (二维坐标)
        B_aug = coords_B  # mx2
        # 最小二乘求解 A_aug * X ≈ B_aug
        # print(A_aug, B_aug)
        transformation_matrix, _, _, _ = lstsq(A_aug, B_aug)  # X: 4×2
        self.extrinsic = transformation_matrix
        self.update_inv_extrinsic_from_lstsq(real_positions, idx)
        # print(f"extrinsic: \n{self.extrinsic}")
        # print(f"👍 Update extrinsic with {points_num}: {idx} markers Success!")
        return transformation_matrix
    
    def update_extrinsic_from_LM(self,markers=None, real_positions=None):
        """
            耗时 0.002506
            markers: 4x4 3D坐标 idx,x,y,z
            real_positions: 4x3 真实位置 idx,x,y
            丢失的位置用-1表示
        """
             
        mask = (markers[:, 0] != -1) & (real_positions[:, 0] != -1) # m>2
        coords_A = markers[mask, 1:]  # mx3
        idx = markers[mask, 0].astype(int) # mx1, aruco标记的id
        coords_B = real_positions[mask, 1:]  # mx2
        coords_B = np.hstack((coords_B, np.ones((coords_B.shape[0], 1))))  # 4x3
        
        points_num = len(coords_A)
        if points_num < self.update_exterinsic_threshold:
            print(f"❌ Not enough markers ({points_num}), "
                  f"need at least {self.update_exterinsic_threshold}")
            return None
        initial_params = np.array([1,0,0,0, 0,1,0,0, 0,0,1,0], dtype=np.float64)
        # 初始参数：单位矩阵，无平移
        res = least_squares(residuals, initial_params, args=(coords_A,coords_B), method='lm')        # 调用最小二乘优化
        self.update_inv_extrinsic_from_lstsq(real_positions, idx)
        self.extrinsic = res.x.reshape(3,4)

        print("👍 Update extrinsic matrix Success!")
        return self.extrinsic
    
    def update_inv_extrinsic_from_lstsq(self,real_positions, idx):
        """
        real_positions: Nx3, 每行 [id, X, Y] 世界坐标
        corners: tuple of arrays, 每个角点 shape (1,4,2)
        """
        # 取检测到的足的像素中心点
        # mask = (markers[:, 0] != -1) & (real_positions[:, 0] != -1) # m>2
        pix_points = []
        corners = self.corners
        idx = idx
        for i, aruco_id in enumerate(idx.flatten()):
            corner = corners[i][0]  # (4,2)
            pix_center = corner.mean(axis=0)  # 足端像素中心
            pix_points.append([aruco_id, pix_center[0], pix_center[1]])
        pix_points = np.array(pix_points)
        
        center_mean = np.mean(pix_points[:,1:],axis=0)
        # print(f"pix_points: \n{pix_points,center_mean}")
        # 对齐两边索引，取交集
        common_ids = np.intersect1d(real_positions[:,0], pix_points[:,0])
        A, B = [], []
        for cid in common_ids:
            real = real_positions[real_positions[:,0]==cid][0,1:]
            pix  = pix_points[pix_points[:,0]==cid][0,1:]
            A.append([real[0], real[1], 1])  # [x,y,1]
            B.append(pix)                    # [u,v]
        A = np.array(A)   # Nx3
        B = np.array(B)   # Nx2
        if len(A) < 2:
            raise ValueError("至少需要2个以上的足才能估算中心位置。")

        # 最小二乘求解仿射矩阵
        M, _, _, _ = np.linalg.lstsq(A, B, rcond=None)  # (3×2)
        self.inv_extrinsic = M

    # -------------------- 坐标转换与检测 -------------------- #
    def get_now_positions(self):
        """
            获取当前位置 4x3, 丢失用-1表示
        """
        return self.now_positions
    
    def get_center_pix(self):
        return self.center
    
    def get_bias(self):
        cx = self.frame_shape[1]//2
        cy = self.frame_shape[0]//2
        dx = int(self.center[0])-cx
        dy = int(self.center[1])-cy
        return [dx,dy]
    
    def get_real_positions(self,drow,dcol):
        """
            保存的图片对应的机器人孔位不一样，根据图片对应的位置解算出机器人绝对位置
        """
        center_row = self.center_row + drow
        center_col = self.center_col + dcol
        real_positions = self._caculate_legs_position(row=center_row, col=center_col, init_flag=False)
        return real_positions 
    
    def position_check(self,now_positions,debug=False):
        """
            now_positions: 4x3 机器人当前位置,idx,x,y,如果丢失则-1,-1,-1
            track的目标是在机器人中心像素center偏离图像中心的大小bias超过阈值时，移动云台使得机器人再画面中心
            然而，像素坐标系下机器人四腿和中心没有明显关系，在真实世界中，四腿的位置是确定的，
            此
            中心像素由当前机器人四腿真实坐标nowposition计算、相机外参矩阵self.extrinsic计算得到
            根据角点的位置，推送机器人中心位置，并且判断中心位置偏离图像中心距离bias,bias超出阈值则返回track=True,
        """
        
        center_real_position,vailable_num = self._calculate_center_position(now_positions)
        center_col = 1 + round((center_real_position[0] *2)/43.301)  # x坐标，
        center_row =1+round((center_real_position[1]*2)/25)  # y坐标
        centers = np.array([center_row,center_col])
        
        # self.extrinsic *self.center
        # A = np.hstack([self.center, np.ones((self.center.shape[0], 1))]) # Mx4
        # # print(f"A: {A}")
        # mapped = A @ self.extrinsic # M×2
        
        
        # 扩展为齐次坐标 (x,y)
        # center_pix = np.dot(np.array([center_real_position[0], center_real_position[1], 1]), self.inv_extrinsic)
        # print(f"center_pix: {center_pix}")
        cx = self.frame_shape[1]//2
        cy = self.frame_shape[0]//2
        dx = int(self.center[0])-cx
        dy = int(self.center[1])-cy
        bias = [dx,dy]
        # print(f"{cx,cy,dx,dy}")
        # if self.track == False:
        #     # 当前静止，大于跟踪阈值且有效aruco多于2个则跟踪 300
        #     threshold = self.start_threshold
        #     self.track = (abs(dx) > threshold or abs(dy) > threshold) and vailable_num>2
        # else:
        #     # 当前运动，都小于停止阈值时停止 100
        #     threshold = self.stop_threshold
        #     self.track =(abs(dx) < threshold and abs(dy) < threshold)
        if not self.track:
        # 处于静止状态 -> 判断是否进入跟踪
            if (abs(dx) >= self.start_threshold or abs(dy) >= self.start_threshold) and vailable_num > 2:
                self.track = True
        else:   
            # 处于跟踪状态 -> 判断是否停止
            if abs(dx) <= self.stop_threshold and abs(dy) <= self.stop_threshold:
                self.track = False
        if debug:
            print(f"now_positions: \n{now_positions}")
            print(f"{self.track,bias,self.center,self.center,center_row,center_col}")
        return self.track,bias,self.center,centers
    
    def apply_affine_lm(self,points,save_position=True):

        if self.extrinsic is None:
            print("Please update extrinsic matrix first")
            extrinsic_npz = np.load(os.path.join(CONFIG_DIR,'extrinsic_matrix.npz'))
            self.extrinsic = extrinsic_npz['extrinsic']

        mapped_points = points[:, :-1] # 第0列为id保持不变 NX3
        # idx表示非-1的行索引
        points,idx = self.get_useful(points)
        idx_r = points[:, 0].astype(int)
        # print(f"mapped_points: {mapped_points}")
        points = points[:, 1:] # 去掉id
        
        A = np.hstack((points, np.ones((points.shape[0], 1)))) # 4x4
        print(f"A: {A.shape}")
        detect_points = np.dot(A, self.extrinsic.T) # 4x3 最后一列全为1
        # return detect_points[:, :2] # 4x2
        mapped_points[idx,1:] = detect_points[:, :2] 
        if save_position:
            self.now_positions = mapped_points
        return mapped_points
    
    def apply_affine_transform(self,points,save_position=True):
        """
            用于将检测的角点坐标映射为世界坐标
            几乎不耗时
            将plane_points_2D转换到世界坐标系下 
            points的变化会影响外部的变化
            输入：points 4x4 3D坐标 idx,x,y,z
            输出：mapped_points 4x3 世界坐标 idx,u,v, 第0列和points保持一致
        """
        if points is None:
            return None
        # points Nx4

        mapped_points = points[:, :-1] # 第0列为id保持不变 NX3
        # idx表示非-1的行索引
        points,idx = self.get_useful(points)
        idx_r = points[:, 0].astype(int)
        # print(f"mapped_points: {mapped_points}")
        points = points[:, 1:] # 去掉id

        if self.extrinsic is None:
            print("Please update extrinsic matrix first")
            extrinsic_npz = np.load(os.path.join(CONFIG_DIR,'extrinsic_matrix.npz'))
            self.extrinsic = extrinsic_npz['extrinsic']
        
        A = np.hstack([points, np.ones((points.shape[0], 1))]) # Mx4
        print(f"A: {A}")
        mapped = A @ self.extrinsic # M×2
        mapped_points[idx,1:] = mapped 
        # print(f"mapped_points: {mapped_points}")
        if save_position:
            self.now_positions = mapped_points
        return mapped_points
    # A = [[-0.30247716,-0.36422648,1.14859131,1.],[-0.67998635,-0.38195501,1.09937052,1.],[-0.67218116,-0.48985796,1.11999488,1.],[-0.30270646,-0.48042111,1.18473472,1]]
    # e_13 = [[1050.73572489,-555.61167445],[-18.19272545,12.27010767],[-90.78275802,3925.69243183],[1826.73771046,-3710.98887328]]
    # e_12=[[974.06049138,104.27103216],[110.85320959,-1196.50187715],[403.43566128,-359.77120179],[1279.32549556,996.71687872]]
    
    def modify_legs_position(self, leg_positions):
        """
            根据行列坐标修改腿部位置
            输入：leg_positions 4x3 行列坐标 idx,x0,y0 丢失则-1,-1，-1
            输出：real_positions 4x3 真实坐标 idx,x,y
        """
        idx = np.where(leg_positions[:, 1] != -1)[0] # 非-1的行索引
        # for i,idx in enumerate(idxs):
        legs_col = 1 + np.round((leg_positions[:,1] *2)/43.301)  # col坐标，
        legs_row = 1 + np.round((leg_positions[:,2] *2)/25)  # row坐标
        
        leg_positions[idx,1] = ((legs_col-1)*43.301/2)[idx]
        leg_positions[idx,2] = ((legs_row-1)*25.0/2)[idx]

        # 补全下面的代码，使得leg_positions为校正后的坐标。
        return leg_positions
    
    
    # -------------------- 精度分析模块 -------------------- #
    def accuracy_estimate(self, real_position, now_positions):
        """
            耗时 0.001-0.0015
            输入：真实位置，当前检测位置进行精度评估
        """
        # localization_error_avg  = np.mean(np.linalg.norm(abs(real_position - now_positions), axis=1))
        # localization_error_l2  = np.max(np.linalg.norm(abs(real_position - now_positions), axis=1))
        foots_error = np.linalg.norm(abs(real_position - now_positions), axis=1)
        idx = np.argmax(np.linalg.norm(abs(real_position - now_positions), axis=1))
        
        foots_error[foots_error>100] = -1
        
        mask = (now_positions[:, 0] != -1) & (real_position[:, 0] != -1)
        real_position = real_position[mask, 1:]  # mx3
        idx = now_positions[mask, 0].astype(int) # mx1, aruco标记的id
        now_positions = now_positions[mask, 1:]  # mx2
        localization_error_avg  = np.mean(np.linalg.norm(abs(real_position - now_positions), axis=1))
        localization_error_l2  = np.max(np.linalg.norm(abs(real_position - now_positions), axis=1))
        print('-------------------------------------------------------')
        print(f'- real position: {real_position},\n now position: {now_positions}')
        print(f'- localization error avg: {localization_error_avg}')
        print(f'- affine_points error l2: {localization_error_l2}')
        print(f'- max idx: {idx}')
        print('- foots error: ' + ', '.join(f'{x:.4f}' for x in foots_error))
        print('-------------------------------------------------------')
        return localization_error_avg, localization_error_l2, foots_error, idx
    
    # -------------------- 工具模块 -------------------- #
    # @staticmethod
    # def _enhance_img(image):
    #     # 图像增强
    #     yuv_image = cv2.cvtColor(image, cv2.COLOR_BGR2YUV) # 2ms
        
    #     # 对Y通道（亮度）进行直方图均衡化
    #     yuv_image[:,:,0] = cv2.equalizeHist(yuv_image[:,:,0])
    #     # # 将图像转换回BGR颜色空间

    #     equalized_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR)
    #     image_gray = cv2.cvtColor(equalized_image, cv2.COLOR_BGR2GRAY)

    #     # 高斯平滑
    #     # gaussian_kernel_size = (5, 5)
    #     # sigma = 0.6 # 0.9
    #     # image_smothed = cv2.GaussianBlur(image_gray, gaussian_kernel_size, sigma)
    #     # image = image_smothed
    #     return image_gray
    @staticmethod
    def _enhance_img(image):
        # 转灰度
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # # CLAHE 自适应直方图均衡
        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        # gray = clahe.apply(gray)

        # # 双边滤波保持边缘
        # gray = cv2.bilateralFilter(gray, d=5, sigmaColor=75, sigmaSpace=75)

        return gray
    @staticmethod
    def _refine_corner(corners,image):
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 30, 0.001)
        corners_refined = []
        for corner in corners:
            corners_refined.append(cv2.cornerSubPix(
                image, corner, (3, 3), (-1, -1), criteria))
        corners_refined = tuple(corners_refined)
        return corners_refined
    
            
    @staticmethod
    def _show_debug(markers_dict):
        # 显示检测的角点坐标
        print("---------------✅ Detected markers---------------")
        for idx, marker in markers_dict.items():
            print(f"Marker {idx}: {marker}")
        print("-------------------------------------------------")
    
    def _show_markers(self, image, corners_sorted, ids_sorted, rvecs, tvecs):
        show_img = image.copy()
        cv2.aruco.drawDetectedMarkers(show_img, corners_sorted, ids_sorted)
        # 根据aruco码的位姿标注出对应的xyz轴
        for r, t in zip(rvecs, tvecs):
            cv2.drawFrameAxes(show_img, self.camera_matrix,
                            self.dist_coeffs, r, t,  self.marker_length, 2)
        # 显示结果
        scale = 0.4
        show_img = cv2.resize(show_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.namedWindow('Markers', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Markers', show_img.shape[1], show_img.shape[0])
        cv2.imshow('Markers', show_img)
        if cv2.waitKey(0) & 0xFF == ord('q'):
            cv2.destroyAllWindows()
    
    @staticmethod
    def get_useful(A):
        lose_idx = np.where(A[:, 0] != -1)[0]
        A_filtered = A[lose_idx]
        return A_filtered,lose_idx
        
    def exit(self):
        cv2.destroyAllWindows()
    

def debug():
    """
        从本地加载图片进行测试aruco定位精度
    """
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    
    # 0.png是初始位置，中心真实坐标为37,18
    # 1.png是向x正向移动一个单位，中心真实坐标为38,18
    # 2.png是向x正向移动二个单位，中心真实坐标为39,18
    # 3.png是向x正向移动三个单位，中心真实坐标为40,18
    img_dir = os.path.join(parent_dir, 'img', "RIGHT")
    # 初始化探测器
    detector = NormalDetector(col=37, row=18)
    # 初始图像（假设0.png为基准）
    frame0 = cv2.imread(os.path.join(img_dir, "0.png"))
    init_list, init_dict, show_img = detector.init_extrinsic(frame0)

    if init_list is None:
        print("❌ 外参初始化失败")
        return
    
    # 测试不同位置
    for i, dx in enumerate([0, 2, 4, 6]):
        print(f"================================{i}================================")
        img_path = os.path.join(img_dir, f"{i}.png")
        frame = cv2.imread(img_path)
        marker_list, marker_dict, show_img = detector.detect_markers(frame)
        if marker_list is None:
            continue
        # print(f"M:{marker_list,marker_dict}")
        now_positions = detector.apply_affine_transform(marker_list, save_position=True)
        real_positions = detector.get_real_positions(dx, 0)  # ground truth
        detector.accuracy_estimate(real_positions, now_positions)
        detector.position_check(now_positions,debug=True)
    detector.exit()



def debug2():
    """
        测试定位平均误差6mm 最大误差10.6mm
        从本地加载图片进行测试aruco定位精度
        img00002.png- img000043.png
        id	y	x    idx
        0	61	77   2
        1	63	77   3
        ...
        41	27	113  43
    """
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    img_dir = os.path.join(parent_dir, 'img', "2025-09-26")
    labels = os.path.join(parent_dir, 'config', 'lables2.xlsx')
    info_path = os.path.join(parent_dir, 'config', 'log44.xlsx')
    df = pd.read_excel(labels)
    print(df.shape)
    info_dic = {
        'id':[],
        'x':[],
        'y':[],
        'foots_error3':[],
        'foots_error2':[],
        'foots_error1':[],
        'foots_error0':[],
        'max_error_number':[],
        'avage_error': [],
        'vaild_number': []
    }

    def data_load(num):
        id = df.loc[num].id
        row = df.loc[num].row
        col = df.loc[num].col
        return int(row), int(col), int(id+2)
    
    init_row,init_col,idx = data_load(0)
    detector = NormalDetector(row=init_row,col=init_col)
    print(init_row,init_col,idx)
    img_name = "img" + "{:05d}".format(idx) + ".png"
    frame0 = cv2.imread(os.path.join(img_dir, img_name))
    init_list, init_dict, show_img = detector.init_extrinsic(frame0)
    def get_drow_dcol(row,col):
        drow = row-init_row
        dcol = col-init_col
        return drow,dcol
    def log_info(id,x,y,foots_error,max_error_number,avage_error,vaild_number):
        info_dic['id'].append(id)
        info_dic['x'].append(x)
        info_dic['y'].append(y)
        info_dic['foots_error3'].append(foots_error[3])
        info_dic['foots_error2'].append(foots_error[2])
        info_dic['foots_error1'].append(foots_error[1])
        info_dic['foots_error0'].append(foots_error[0])
        info_dic['max_error_number'].append(max_error_number)
        info_dic['avage_error'].append(avage_error)
        info_dic['vaild_number'].append(vaild_number)
    
    if init_list is None:
        print("❌ 外参初始化失败")
        return
    
    for i in range(0,25):
        print(f"================================{i}================================")
        row,col,idx = data_load(i)
        
        drow,dcol = get_drow_dcol(row,col)
        print(row,col,idx)
        img_name = "img" + "{:05d}".format(idx) + ".png"
        frame = cv2.imread(os.path.join(img_dir, img_name))
        marker_list, marker_dict, show_img = detector.detect_markers(frame)
        if marker_list is None:
            continue
        vaild_number = len(np.where(marker_list[:, 0] != -1)[0])
        now_positions = detector.apply_affine_transform(marker_list, save_position=True)
        print(f"detect_positions: {now_positions}")
        real_positions = detector.get_real_positions(drow, dcol)  # ground truth
        avage_error, localization_error_l2, foots_error, max_error_number = detector.accuracy_estimate(real_positions, now_positions)
        detector.position_check(now_positions,debug=True)
        log_info(idx,row,col,foots_error,max_error_number,avage_error,vaild_number)
    info = pd.DataFrame(info_dic)
    info.to_excel(info_path, sheet_name='Sheet1', index=False)
    detector.exit()

def debug3():
    """
        从本地加载图片进行测试aruco定位精度,
        测试逆定位精度：100%
        img00002.png- img000043.png
        id	y	x    idx
        0	61	77   2
        1	63	77   3
        ...
        41	27	113  43`
        
        id    cx      cy
        2     1800    820
        3     1800    800
        4     1800    760
        20    670     600
        21    650     760
        22    630     900
        
        39    2780    1690
        40    3000    1720
        41    3100    1700
    """
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    img_dir = os.path.join(parent_dir, 'img', "2025-09-26")
    print(img_dir)
    labels = os.path.join(parent_dir, 'config', 'lables2.xlsx')
    print(labels)
    info_path = os.path.join(parent_dir, 'config', 'info2.xlsx')
    df = pd.read_excel(labels)
    
    def data_load(num):
        id = df.loc[num].id
        col = df.loc[num].col
        row = df.loc[num].row
        return row, col, id+2
    
    init_row,init_col,idx = data_load(0)
    detector = NormalDetector(row=init_row,col=init_col)
    img_name = "img" + "{:05d}".format(idx) + ".png"
    frame0 = cv2.imread(os.path.join(img_dir, img_name))
    init_list, init_dict, show_img = detector.init_extrinsic(frame0)
    def get_drow_dcol(row,col):
        drow = row-init_row
        dcol = col-init_col
        return drow,dcol
    
    if init_list is None:
        print("❌ 外参初始化失败")
        return
    
    for i in range(0,25):
        print(f"================================{i}================================")
        row,col,idx = data_load(i)
        drow,dcol = get_drow_dcol(row,col)
        
        img_name = "img" + "{:05d}".format(idx) + ".png"
        print(row,col,idx)
        frame = cv2.imread(os.path.join(img_dir, img_name))
        # cv2.imshow("frame",frame)
        # cv2.waitKey(0)
        marker_list, marker_dict, show_img = detector.detect_markers(frame)
        if marker_list is None:
            continue
        vaild_number = len(np.where(marker_list[:, 0] != -1)[0])
        now_positions = detector.apply_affine_transform(marker_list, save_position=True)
        real_positions = detector.get_real_positions(drow, dcol)  # ground truth
        avage_error, localization_error_l2, foots_error, max_error_number = detector.accuracy_estimate(real_positions, now_positions)
        detector.position_check(now_positions,debug=True)

    detector.exit()

def get_drow_dcol(row,col,init_row,init_col):
    drow = row-init_row
    dcol = col-init_col
    return drow,dcol

def debug4():
    """
        从本地加载图片进行测试aruco定位精度, 动态更新外参 平均偏差3.16mm, 最大偏差26.2mm
    """
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    img_dir = os.path.join(parent_dir, 'img', "2025-09-26")
    labels = os.path.join(parent_dir, 'config', 'lables2.xlsx')
    info_path = os.path.join(parent_dir, 'config', 'update_log44.xlsx')
    df = pd.read_excel(labels)
    info_dic = {
        'id':[],
        'x':[],
        'y':[],
        'foots_error3':[],
        'foots_error2':[],
        'foots_error1':[],
        'foots_error0':[],
        'max_error_number':[],
        'avage_error': [],
        'vaild_number': []
    }

    def data_load(num):
        id = df.loc[num].id
        col = df.loc[num].col
        row = df.loc[num].row
        return int(row), int(col), int(id+2)
    
    init_row,init_col,idx = data_load(0)
    detector = NormalDetector(row=init_row,col=init_col)
    img_name = "img" + "{:05d}".format(idx) + ".png"
    frame0 = cv2.imread(os.path.join(img_dir, img_name))
    init_list, init_dict, show_img = detector.init_extrinsic(frame0)
    

    def log_info(id,x,y,foots_error,max_error_number,avage_error,vaild_number):
        info_dic['id'].append(id)
        info_dic['x'].append(x)
        info_dic['y'].append(y)
        info_dic['foots_error3'].append(foots_error[3])
        info_dic['foots_error2'].append(foots_error[2])
        info_dic['foots_error1'].append(foots_error[1])
        info_dic['foots_error0'].append(foots_error[0])
        info_dic['max_error_number'].append(max_error_number)
        info_dic['avage_error'].append(avage_error)
        info_dic['vaild_number'].append(vaild_number)
    
    if init_list is None:
        print("❌ 外参初始化失败")
        return
    update_flag = True
    update_from_mapped = False
    for i in range(0,25):
        # i=13时更新的外参有问题，导致之后的偏差累积
        print(f"================================{i}================================")
        row,col,idx = data_load(i)
        drow,dcol = get_drow_dcol(row,col,init_row,init_col)
        print(init_row,init_col,row,col,drow,dcol)
        img_name = "img" + "{:05d}".format(idx) + ".png"
        print("frame:",img_name)
        frame = cv2.imread(os.path.join(img_dir, img_name))
        marker_list, marker_dict, show_img = detector.detect_markers(frame)
        if marker_list is None:
            continue
        vaild_number = len(np.where(marker_list[:, 0] != -1)[0])
        now_positions = detector.apply_affine_transform(marker_list.copy(), save_position=True)
        real_positions = detector.get_real_positions(drow, dcol)  # ground truth
        avage_error, localization_error_l2, foots_error, max_error_number = detector.accuracy_estimate(real_positions, now_positions)
        _,_,_,centers = detector.position_check(now_positions.copy(),debug=True)
        print(centers)
        if update_flag:
            if update_from_mapped:
                detector.update_extrinsic_from_lstsq(marker_list, now_positions)
            else:
                drow,dcol = get_drow_dcol(centers[0],centers[1],init_row,init_col)
                print(init_row,init_col,centers[0],centers[1],drow,dcol)
                up_positions = detector.get_real_positions(drow, dcol)
                # 或直接real_positions
                detector.update_extrinsic_from_lstsq(marker_list, real_positions)
            init_row,init_col = row,col
            detector.center_row = init_row
            detector.center_col = init_col
        log_info(idx,row,col,foots_error,max_error_number,avage_error,vaild_number)
    info = pd.DataFrame(info_dic)
    info.to_excel(info_path, sheet_name='Sheet1', index=False)
    detector.exit()

if __name__ == '__main__':
    debug3()