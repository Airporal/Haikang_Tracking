import cv2
import numpy as np
from scipy.linalg import lstsq
from scipy.optimize import least_squares
import time
from detecter_help import *
import os
class locator:
    def __init__(self, intrinsic_npz:str,draw_flag=True):
        ## 加载相机内参和畸变参数
        camera_data = np.load(intrinsic_npz)
        self.camera_matrix = camera_data['camera_matrix']
        self.dist_coeffs = camera_data['dist_coeffs']
        
        self.marker_length = 0.041 # aruco标记边长 in meters
        self.draw_flag = draw_flag  # 绘图
        
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        self.extrinsic = None
        
        self.update_exterinsic_threshold = 3  # 用于记录更新外参的aruco码数量阈值
        
        self.now_positions = None
    
    # -------------------- aruco检测模块 -------------------- #
    # @stopwatch
    def detect_markers(self, image_file, update=False):
        """
            耗时90ms
            检测aruco码并返回aruco码的3D坐标和姿态估计
            确保markers的顺序与初始标定一致
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

            # 从大到小排列
            sorted_indices = np.argsort(ids.flatten())[::-1]
            corners_sorted = [corners[i] for i in sorted_indices]
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
            # self._show_debug(marker_dict)
            if update==True:
                self.markers = np.array(marker_list) # 用于更新参数
            if self.draw_flag:
                # 此处耗时8ms
                self._show_markers(show_img, corners_sorted, ids_sorted, rvecs, tvecs)
                # show_3D(self.markers)
            return marker_list, marker_dict
        else:
            return None, None
        
    def get_pos_2D(self,points, mode=3,save_position=True):
        """
            用于直接获取映射后的2D坐标点,
            不移动时，设置save_position=True，会记录当前获取的位置，用于后续更新外参
        """
        if points == None:
            return None
        affine_points = get_2D_plane_pos(points, use_ABCD=True) # 4x2
        mapped_points = None
        if mode == 2:
            # 2D
            mapped_points = self.apply_affine_transform_2D(affine_points) # 4x2
        elif mode == 3:
            # lstsq or LM
            mapped_points = self.apply_affine_transform(affine_points) # 4x2
        else:
            print("mode error")
        if save_position:
            # 遮住aruco码不保存位置，只保存完整的位置
            if len(mapped_points)==4:
                self.now_positions = mapped_points
            # print("now_positions:",self.now_positions)
        return mapped_points
    # -------------------- 外参校准模块 -------------------- #
    # @stopwatch
    def update_extrinsic_from_lstsq(self, img_num=None,real_positions=None):
        """
            耗时 0.001189
            detect_markers 之后调用，更新外参矩阵，detect的aruco码数量大于等于update_exterinsic_threshold才更新
            同时，detect_markers检测结果确保与初始标定顺序一致
            采用AX=B计算投影平面到管板世界坐标系的二维位置的转移矩阵
            使用此矩阵X 可以将plane_points_2D 转换到世界坐标系下
        """
        if real_positions is None:
            real_positions = self._get_real_positions(img_num) # 设置真实位置
        else:
            real_positions = real_positions
        # print(f"real_positions: {real_positions}")
        
        # 只保留当前检测到的 marker 对应的真实位置
        # self.markers 和 ids_sorted 保持一致，这里 ids[i] 与 markers[i] 对应
        detected_markers_2D = get_2D_plane_pos(self.markers, False)  # N×2
        # print(f"detected_markers_2D: {detected_markers_2D}")
        if len(detected_markers_2D) < self.update_exterinsic_threshold:
            print(f"❌ Not enough markers ({len(detected_markers_2D)}), "
                  f"need at least {self.update_exterinsic_threshold}")
            return None
        # 按照数量截取
        valid_num = len(detected_markers_2D)
        A = np.hstack((detected_markers_2D, np.ones((valid_num, 2))))   # N×3 
        B = np.hstack((real_positions[:valid_num], np.ones((valid_num, 1))))  # N×3
        
        transformation_matrix, _, _, _ = lstsq(A, B) # transformation_matrix 4x3 包含旋转与平移
        self.extrinsic = np.vstack((transformation_matrix.T,np.array([0,0,0,1]))) # 更新外参矩阵4X4
        print(f"👍 Update extrinsic with {valid_num} markers Success!")
        return self.extrinsic
    
    # @stopwatch
    def update_extrinsic_from_LM(self, img_num=None,real_positions=None):
        """
            耗时 0.002506
            使用LM方法更新外参矩阵 0.
        """
        if real_positions is None:
            real_positions = self._get_real_positions(img_num) # 设置真实位置
        else:
            real_positions = real_positions        
        self.markers_2D = get_2D_plane_pos(self.markers,False)
        src_2D_points_1 = np.hstack((self.markers_2D, np.ones((self.markers_2D.shape[0], 1)))) # 4x3
        real_2D_points_1 = np.hstack((real_positions, np.ones((real_positions.shape[0], 1))))  # 4x3

        # 初始参数：单位矩阵，无平移
        initial_params = np.array([1,0,0,0, 0,1,0,0, 0,0,1,0], dtype=np.float64)
        # 调用最小二乘优化
        result = least_squares(residuals, initial_params, method='lm', 
                           args=(src_2D_points_1, real_2D_points_1))
        # 提取优化后的参数
        optimized_params = result.x
        # 构建仿射矩阵
        affine_matrix = np.array([
            optimized_params[:4],
            optimized_params[4:8],
            optimized_params[8:12],
            [0.0, 0.0, 0.0, 1.0]
        ]) # 4x4
        self.extrinsic = affine_matrix
        # np.savez(os.path.join(CONFIG_DIR,'extrinsic_matrix.npz'), extrinsic=self.extrinsic)
        print("👍 Update extrinsic matrix Success!")
        return self.extrinsic
    
    # @stopwatch
    def update_extrinsic_2D(self,img_num=None,real_positions=None):
        """
        耗时 0.001505
        根据先验anchor的坐标和圆孔行列计算新的marker所插圆孔位置
        prior_achrs: 锚点二维坐标，[x, y]
        prior_holes: 锚点圆孔行列，[x, y]
        marker_new : 新标记点
        """
        if real_positions is None:
            real_positions = self._get_real_positions(img_num) # 设置真实位置
        else:
            real_positions = real_positions   
        self.markers_2D = get_2D_plane_pos(self.markers,False)
        
        ## 计算先验achrs -> holes的映射
        # 构建线性方程组的矩阵
        A = np.zeros((2 * len(self.markers_2D), 6))
        B = np.zeros((2 * len(self.markers_2D), 1))
        for i, (x, y) in enumerate(self.markers_2D):
            A[2 * i, :] = [x, y, 0, 0, 1, 0]
            A[2 * i + 1, :] = [0, 0, x, y, 0, 1]
            B[2 * i] = real_positions[i][0]
            B[2 * i + 1] = real_positions[i][1]
        # 求解最小二乘问题
        X, _, _, _ = lstsq(A, B)
        # 提取变换矩阵的元素
        a, b, c, d, tx, ty = X.flatten()
        # 构建变换矩阵
        self.extrinsic_2D = np.array([[a, b, tx], [c, d, ty], [0, 0, 1]])
        return self.extrinsic_2D
    
    # -------------------- 外参测试模块 -------------------- #
    def apply_affine_transform(self,points):
        """
            几乎不耗时
            将plane_points_2D转换到世界坐标系下 
            输入：plane_points_2D 4x2
            输出：real_2D_points 4x3
        """
        if self.extrinsic is None:
            print("Please update extrinsic matrix first")
            extrinsic_npz = np.load(os.path.join(CONFIG_DIR,'extrinsic_matrix.npz'))
            self.extrinsic = extrinsic_npz['extrinsic']
        A = np.hstack((points, np.ones((points.shape[0], 2)))) # 4x4
        detect_points = np.dot(A, self.extrinsic.T) # 4x3 最后一列全为1
        return detect_points[:, :2] # 4x2

    def apply_affine_transform_2D(self,points):
        """
            几乎不耗时
            根据plane_points_2D到marker的映射关系，直接计算marker的插圆孔位置
            points: aruco码的plane_points_2D坐标
        """
        # 计算新的marker插的圆孔
        result_list = []
        for marker_new in points:
            # 将新的点转换为齐次坐标
            new_point_homogeneous = np.array([[marker_new[0]], [marker_new[1]], [1]])
            # 应用变换矩阵
            mapped_point_homogeneous = self.extrinsic_2D @ new_point_homogeneous
            # 从齐次坐标转换回二维坐标
            mapped_point = mapped_point_homogeneous[:2, 0]
            result_list.append(mapped_point)
        return np.vstack(result_list)
    
    @staticmethod
    def _get_real_positions(img_num):
        """
            保存的图片对应的机器人孔位不一样，根据图片对应的位置解算出机器人绝对位置
        """
        # 设置初始化机器足圆孔位置,机器人中心位置,机器人四个足端位置
        robot_c  = np.array([526.311, 787.5]) # 机体中心
        leg_dev  = np.array([64.9515, 150])
        leg_quad = np.array([[1, -1], [1, 1], [-1, 1], [-1, -1]])
        prior_devia = leg_quad * leg_dev
        prior_holes = robot_c + prior_devia
        
        # 运动位移[x, y]
        motion_dev   = np.array([43.301, 25])
        motion_right = np.array([-1, 0])
        motion_down  = np.array([0, -1])
        
        # 每个图片对应的位置机器人位置不一样，由此针对不同图片计算位置
        if img_num <= 13:
            gt_leg_res = prior_holes + (img_num - 1) * motion_down * motion_dev
        elif img_num > 13:
            gt_leg_res = prior_holes + 12 * motion_down * motion_dev
            gt_leg_res = gt_leg_res + (img_num - 13) * motion_right * motion_dev
        return gt_leg_res
    
    def get_now_positions(self):
        """
            获取累积的位置变化, 用于重新校准外参
            机器人Arcuco码缺失->获取当前的位置->移动相机云台->停止移动->获取新的aruco码->根据之前记录的位置跟新外参
        """
        return self.now_positions
    # -------------------- 精度分析模块 -------------------- #
    def accuracy_estimate(self, points, image_num, mode = 2):
        """
            耗时 0.001-0.0015
            计算精度, 输入aruco码的检测坐标列表, 图像的真实坐标，返回精度评估值
            points: aruco码的二维坐标新监测的点
            image_num: 图像编号，用于获取真实坐标
        """
        real_points = self._get_real_positions(image_num) # 4x2
        affine_points = get_2D_plane_pos(points, use_ABCD=True) # 4x2
        if mode == 2:
            # 2D
            mapped_points = self.apply_affine_transform_2D(affine_points) # 4x2
        elif mode == 3:
            # lstsq or LM
            mapped_points = self.apply_affine_transform(affine_points) # 4x2
        else:
            print("mode error")
        
        localization_error_avg  = np.mean(np.linalg.norm(abs(real_points - mapped_points), axis=1))
        localization_error_l2  = np.max(np.linalg.norm(abs(real_points - mapped_points), axis=1))
        foots_error = np.linalg.norm(abs(real_points - mapped_points), axis=1)
        idx = np.argmax(np.linalg.norm(abs(real_points - mapped_points), axis=1))
        
        print('-------------------------------------------------------')
        print(f'- localization error avg: {localization_error_avg}')
        print(f'- affine_points error l2: {localization_error_l2}')
        print(f'- max idx: {idx}')
        print(f'- foots error:\n{foots_error}')
        print('-------------------------------------------------------')
        return localization_error_avg, localization_error_l2, foots_error, idx

    # -------------------- 工具模块 -------------------- #
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
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()
    
    @staticmethod
    def _show_debug(markers_dict):
        # 显示检测的角点坐标
        print("---------------✅ Detected markers---------------")
        for idx, marker in markers_dict.items():
            print(f"Marker {idx}: {marker}")
        print("-------------------------------------------------")
        
    @staticmethod
    def _refine_corner(corners,image):
        # 角点增强
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_refined = []
        for corner in corners:
            corners_refined.append(cv2.cornerSubPix(
                image, corner, (3, 3), (-1, -1), criteria))
        corners_refined = tuple(corners_refined)
        return corners_refined
    
    @staticmethod
    def _enhance_img(image):
        # 图像增强
        yuv_image = cv2.cvtColor(image, cv2.COLOR_BGR2YUV) # 2ms
        
        # 对Y通道（亮度）进行直方图均衡化
        yuv_image[:,:,0] = cv2.equalizeHist(yuv_image[:,:,0])
        # # 将图像转换回BGR颜色空间

        equalized_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR)
        image_gray = cv2.cvtColor(equalized_image, cv2.COLOR_BGR2GRAY)

        # 高斯平滑
        gaussian_kernel_size = (5, 5)
        sigma = 0.6 # 0.9
        image_smothed = cv2.GaussianBlur(image_gray, gaussian_kernel_size, sigma)
        image = image_smothed
        return image


    
if __name__ == '__main__':
    current_dir = os.path.dirname(__file__)
    # 父目录
    parent_dir = os.path.dirname(current_dir)
    INTRINSIC = os.path.join(parent_dir, 'config','camera_calibration.npz')
    img_dir = os.path.join(parent_dir, 'img','camera_tilt')
    src_img_num = 1
    locator = locator(INTRINSIC)
    while src_img_num <= 10:
        dst_img_num = src_img_num + 1
        src_image_file = os.path.join(img_dir, str(src_img_num) + '.jpg')
        dst_image_file = os.path.join(img_dir, str(dst_img_num) + '.jpg')
        src_3D_points, src_marker_dict = locator.detect_markers(src_image_file, update=True)
        dst_3D_points, dst_marker_dict = locator.detect_markers(dst_image_file, update=False)   
        # 更新外参
        # extrinsic_lm = locator.update_extrinsic_from_LM(src_img_num) 
        # locator.accuracy_estimate(dst_3D_points, dst_img_num, mode = 3) 
        # extrinsic_2D = locator.update_extrinsic_2D(src_img_num) 
        # locator.accuracy_estimate(dst_3D_points, dst_img_num, mode = 2) 
        extrinsic_lstsq = locator.update_extrinsic_from_lstsq(src_img_num) 
        locator.accuracy_estimate(dst_3D_points, dst_img_num, mode = 3)
        
    
        src_img_num +=1
        
     