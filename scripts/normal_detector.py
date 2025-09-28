import cv2
import json
import os
import numpy as np
from pyzbar import pyzbar
from location import locator

DETECTOR_SET = {
    "kcf": lambda: cv2.TrackerKCF.create(),
    "medianflow": lambda: cv2.legacy.TrackerMedianFlow.create(),
    "mosse": lambda: cv2.legacy.TrackerMOSSE.create(),
    "boosting": lambda: cv2.legacy.TrackerBoosting.create(),
    "tld": lambda: cv2.legacy.TrackerTLD.create(),
    "mil": lambda: cv2.TrackerMIL.create(),
    "csrt": lambda: cv2.TrackerCSRT.create(),
    # "goturn":lambda: cv2.TrackerGOTURN.create(), prototxt模型
    # "vit":lambda: cv2.TrackerVit.create(), ONNX模型
    # "nano":lambda: cv2.TrackerNano.create(),  # ONNX模型
    # "dasiamrpn":lambda: cv2.TrackerDaSiamRPN.create(),  # ONNX模型
}
class NormalDetector:
    def __init__(self, model="boosting", from_video=True):
        self.model = model
        self.tracker = DETECTOR_SET[self.model]()
        self.from_video = from_video
        self.cap = None
        self.frame = None
        self.bbox = None
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_dir = os.path.dirname(current_dir)
        self.bbox_path = os.path.join(self.project_dir, "config", "bbox.json")
        self.target_img_path = os.path.join(self.project_dir, "config", "template.jpg")
        # 给一个初始的位置用于确定外参 4x2，对应0-1-2-3
        self.init_locator()
        if not np.all(self.mylocator.now_positions == 0):
            self.init_positions = self.mylocator.now_positions
            print(f"✅ 初始位置: {self.init_positions}")
        else:
            self.init_positions = np.array([
                [0,0],
                [0,0],
                [0,0],
                [0,0],
            ])
            print(f"❌ 初始位置未设置，使用默认值: {self.init_positions}")
        
        
    def init_locator(self):
        """
            初始化定位器
        """
        INTRINSIC = os.path.join(self.project_dir, 'config','camera_calibration.npz')
        self.Locator_initFlag = False # 当有第一个外参矩阵后标记为True
        self.mylocator = locator(INTRINSIC)

    def init_extrinsic(self, frame):
        # 初始化校准外参矩阵，根据初始测量位置计算外参矩阵
        init_3D_points, init_marker_dict, show_img = self.mylocator.detect_markers(image_file = frame, update=True)
        if init_3D_points is not None:
            print(f"{self.init_positions}")
            if not np.array_equal(self.init_positions, np.array([[0,0],[0,0],[0,0],[0,0]])):
                self.mylocator.update_extrinsic_from_lstsq(real_positions=self.init_positions)
            else:
                self.mylocator.update_extrinsic_from_lstsq(real_positions=self.mylocator.now_positions)
            self.Locator_initFlag = True
        else:
            print("❌ 初始外参矩阵计算失败，请检查初始位置")
        return init_3D_points, init_marker_dict
        
    def load_bbox_from_file(self, bbox_path):
        if bbox_path and os.path.exists(bbox_path):
            with open(bbox_path, "r") as f:
                return tuple(json.load(f))
        return None
    
    # 尺度金字塔
    def multi_scale_match(self, frame, template, scales=[0.9, 1.0, 1.1]):
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        best_val = -1
        best_bbox = None

        for scale in scales:
            resized = cv2.resize(template, (0, 0), fx=scale, fy=scale)
            if resized.shape[0] > gray_frame.shape[0] or resized.shape[1] > gray_frame.shape[1]:
                continue
            result = cv2.matchTemplate(gray_frame, cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY), cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_bbox = (*max_loc, resized.shape[1], resized.shape[0])

        if best_val < 0.35:
            print(f"❌ 多尺度模板匹配失败，最大得分: {best_val:.3f}")
            return None
        print(f"✅ 多尺度匹配成功，得分: {best_val:.3f}, bbox: {best_bbox}")
        return best_bbox
    
    # 模板匹配
    def match_target_image(self, frame, target_img_path):
        template = cv2.imread(target_img_path)
        if template is None:
            print("❌ 无法读取目标图像")
            return None

        bbox = self.multi_scale_match(frame, template)
        if bbox is None:
            return None

        x, y, w, h = [int(v) for v in bbox]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow("Template Match", frame)
        cv2.waitKey(1000)
        cv2.destroyWindow("Template Match")
        return bbox
    
    # ORB 特征匹配
    def orb_match_bbox(self, frame, template, min_match_count=10):
        img1 = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        img2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        orb = cv2.ORB.create(nfeatures=500)
        # orb = cv2.ORB_create()
        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)

        if des1 is None or des2 is None:
            print("❌ 无法提取 ORB 特征")
            return None

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)

        if len(matches) < min_match_count:
            print(f"❌ ORB 匹配失败，匹配点数不足: {len(matches)}")
            return None

        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            print("❌ 单应矩阵估计失败")
            return None

        h, w = img1.shape
        pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(pts, M)
        x, y, w, h = cv2.boundingRect(np.int32(dst))
        print(f"✅ ORB 匹配成功: {(x, y, w, h)}")
        return (x, y, w, h)

    def save_template(self, frame, bbox, save_path="template.jpg"):
        x, y, w, h = [int(i) for i in bbox]
        cropped = frame[y:y + h, x:x + w]
        if cropped.size == 0:
            print("❌ 裁剪区域为空，未保存模板")
            return
        os.makedirs(os.path.dirname(save_path), exist_ok=True) if os.path.dirname(save_path) else None
        cv2.imwrite(save_path, cropped)
        print(f"📸 模板图像已保存: {save_path}")

    def save_bbox(self):
        os.makedirs(os.path.dirname(self.bbox_path), exist_ok=True)
        if self.bbox:
            with open(self.bbox_path, "w") as f:
                json.dump(list(self.bbox), f)
            print(f"💾 bbox 已保存到 {self.bbox_path}")

    def init_detector_from_video(self, video_path=0, **kwargs):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print("❌ 摄像头/视频打开失败")
            exit()
        ret, frame = self.cap.read()
        if not ret:
            print("❌ 无法读取第一帧")
            exit()
        self.init_tracker_on_frame(frame, **kwargs)

    def init_detector_from_frame(self, frame, **kwargs):
        if frame is None or frame.size == 0:
            print("❌ 提供的初始化帧无效")
            exit()
        return self.init_tracker_on_frame(frame, **kwargs)

    def selectROI_scaled(self,window_name, img, scale=0.3):
        # Step1: Resize 显示图像
        scaled_img = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        cv2.imshow(window_name, scaled_img)

        # Step2: 手动选择目标框（在缩放图上）
        roi = cv2.selectROI(window_name, scaled_img, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow(window_name)

        # Step3: 将选择的 ROI 映射回原图坐标
        x, y, w, h = roi
        x = int(x / scale)
        y = int(y / scale)
        w = int(w / scale)
        h = int(h / scale)
        return (x, y, w, h)

    def init_tracker_on_frame(self, frame, manual=False, load_bbox_from_file=False,
                              target_match=False, feature_match=False, save_bbox=False,reinit_on_lost=False):
        self.frame = frame
        bbox = None
        init_marker_dict = None
        # 初始化校准外参矩阵，根据初始测量位置计算外参矩阵, 如果重新跟踪目标，则不更新外参矩阵
        if not reinit_on_lost:
            init_3D_points, init_marker_dict = self.init_extrinsic(frame)
        if manual:
            print("🟢 手动选择目标框...")
            bbox = self.selectROI_scaled("Choose Target and press SPACE", frame)
            # bbox = cv2.selectROI("Choose Target and press SPACE", frame, fromCenter=False)
            # cv2.destroyWindow("Choose Target and press SPACE")
        elif load_bbox_from_file:
            bbox = self.load_bbox_from_file(self.bbox_path)
            if bbox:
                print(f"🟢 从文件加载目标框: {bbox}")
        elif target_match:
            print(f"🟢 从目标图像匹配中初始化")
            bbox = self.match_target_image(frame, self.target_img_path)
        elif feature_match:
            print("🟢 使用 ORB 特征匹配初始化...")
            template = cv2.imread(self.target_img_path)
            if template is not None:
                bbox = self.orb_match_bbox(frame, template)

        if not bbox or bbox[2] == 0 or bbox[3] == 0:
            print("❌ 无法获取有效目标框")
            exit()

        self.bbox = bbox
        self.tracker = DETECTOR_SET[self.model]()
        self.tracker.init(frame, bbox)
        
        if save_bbox:
            self.save_bbox()
            self.save_template(frame, bbox, save_path=self.target_img_path)

        print("✅ Tracker 初始化完成")
        return init_marker_dict

    def detect(self, frame=None, reinit_on_lost=True, save_position=False,update=False):
        """
          云台不移动时才可以设置save_position=True，此时会根据之前的位置更新当前目标真实位置，如果云台移动则会导致坐标偏移
          更新外参时才设置update=True，会保存当前检测框锚点的相机坐标系检测坐标
          9.22 当没有aruco标记时，返回mapped_points=None
          9.22 添加了show_frame，用于显示检测框和标记点
        """
        if frame is None:
            
            if self.cap:
                ret, frame = self.cap.read()
                if not ret:
                    print("❌ 无法读取视频帧")
                    return None, None, None, None, None
            else:
                print("❌ 未提供帧，且未绑定视频源")
                return None, None, None,None, None
        
        success, box = self.tracker.update(frame)
        
        # 默认不更新markers,当需要更新外参时更新
        # try:
        frame_3D_points, frame_marker_dict, show_frame = self.mylocator.detect_markers(frame,update=update)
        
        # print(f"🔍 检测到{frame_marker_dict,frame_3D_points,result}个标记点")
        if frame_3D_points is not None:
            mapped_points = self.mylocator.get_pos_2D(frame_3D_points,save_position=save_position)
            mapped_points = np.array([[k, *v] for k, v in zip(frame_marker_dict.keys(), mapped_points)])
        else:
            mapped_points = None

        # mapped_points = None
        if success:
            self.bbox = box
            center = self.get_box_center(box)
            cv2.rectangle(show_frame, (int(box[0]), int(box[1])),
                          (int(box[0] + box[2]), int(box[1] + box[3])),
                          (0, 255, 0), 2)

            return frame, box, center, mapped_points, show_frame
        else:
            cv2.putText(frame, "Tracking Lost", (50, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
            print("⚠️ 目标丢失！")
            if reinit_on_lost and self.frame is not None:
                print("🔁 重新初始化 Tracker")
                self.init_tracker_on_frame(self.frame, manual=True, reinit_on_lost=True)
            return frame, None, None,None, frame

    def redetect(self, frame=None, mode = 2):
        """
          重新检测目标，用于目标位置更新，新的bbox将会被保存。
        """
        if mode == 0:
            # 直接加载保存的初始框，用于手动测量后加载
            box = self.init_tracker_on_frame(frame,load_bbox_from_file=True,reinit_on_lost=True)
        elif mode == 1:
            # 使用保存的特征图模板匹配对象
            box = self.init_tracker_on_frame(frame,target_match=True,reinit_on_lost=True)
        elif mode == 2:
            # 使用保存得到特征图特征匹配
            box = self.init_tracker_on_frame(frame,feature_match=True,reinit_on_lost=True)
        elif mode == 3:
            box = self.init_tracker_on_frame(frame,manual=True,reinit_on_lost=True)
    
    def get_box_center(self, box):
        x, y, w, h = box
        return (x + w // 2, y + h // 2)

    def exit(self):
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

def test_video():
    det = NormalDetector(model="boosting", from_video=True)
    det.init_detector_from_video(video_path=0, manual=True,save_bbox=True)
    while True:
        frame, box, center, number, _ = det.detect()
        print(center,number)
        if frame is None:
            break
        cv2.imshow("Tracking", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    det.exit()

# def test_frame():
#     frame = cv2.imread("test.jpg")
#     det = NormalDetector(model="boosting", from_video=False)
#     det.init_detector_from_frame(frame, target_match=True)
#
#     # 可用于循环调用
#     while True:
#         # 假设你从其他系统不断获取帧
#         new_frame = get_external_frame()
#         frame, box, center = det.detect(new_frame)
#         cv2.imshow("Tracking", frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break
#     det.exit()

if __name__ == '__main__':
    test_video()