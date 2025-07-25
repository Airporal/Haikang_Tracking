import cv2
import json
import os
import numpy as np

# DETECTOR_SET = {
#     "kcf":cv2.TrackerKCF.create(), # 抖动，速度快 0.031
#     "medianflow":cv2.legacy.TrackerMedianFlow.create(), # 非常稳0.04
#     "mosse":cv2.legacy.TrackerMOSSE.create(), # 轻量，容易出bug0.036
#     "boosting":cv2.legacy.TrackerBoosting.create(),# 稳定，速度快0.029
#     "tld":cv2.legacy.TrackerTLD.create(), # 稳定，速度快,精度低 0.038
#     "mil":cv2.TrackerMIL.create(), # 较稳定，卡顿 0.045
#     "csrt":cv2.TrackerCSRT.create(), # 抖动 0.040
#     # "goturn":cv2.TrackerGOTURN.create(), prototxt模型
#     # "vit":cv2.TrackerVit.create(), ONNX模型
#     # "nano":cv2.TrackerNano.create(),  # ONNX模型
#     # "dasiamrpn":cv2.TrackerDaSiamRPN.create(),  # ONNX模型
# }
# 改成函数，而不是创建好的对象
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
# 调用时使用：
# self.tracker = DETECTOR_SET[self.model]()  # 注意括号

class NormalDetector:
    def __init__(self,model="boosting"):
        self.model = model
        self.tracker = DETECTOR_SET[self.model]()
        self.cap = None
        self.bbox = None
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_dir = os.path.dirname(current_dir)
        self.bbox_path = os.path.join(self.project_dir, "config", "bbox.json")
        self.target_img_path = os.path.join(self.project_dir, "config", "test2.png")

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

    def selectROI_scaled(self,window_name, img, scale=0.5):
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


    def init_detector(self, new_frame=None, video_path=-1, manual=False, load_bbox_from_file=False, target_match=False,feature_match=True, save_bbox=False):
        # None时开始初始化，其它时重新加载
        if self.cap is None:
            if video_path==-1:
                frame=new_frame
            else:
                self.cap = cv2.VideoCapture(video_path)
                if not self.cap.isOpened():
                    print("❌ 摄像头/视频打开失败")
                    exit()
        if video_path==-1:
            frame = new_frame
            ret = 1
        else:
            ret, frame = self.cap.read()
        if not ret:
            print("❌ 无法读取第一帧")
            exit()

        self.frame = frame  # 记录第一帧

        # --- 1. 初始化 bbox ---
        bbox = None

        # Case1: 手动框选
        if manual:
            print("🟢 手动选择目标框...")
            bbox = self.selectROI_scaled("Choose Target and press SPACE", frame)
            # bbox = cv2.selectROI("Choose Target and press SPACE", frame, fromCenter=False)
            # cv2.destroyWindow("Choose Target and press SPACE")
        # Case2: 从文件框 需要保障开启位置一致
        elif load_bbox_from_file:
            bbox = self.load_bbox_from_file(self.bbox_path)
            if bbox:
                print(f"🟢 从文件加载目标框: {bbox}")
        # Case3: 模板匹配
        elif target_match:
            print(f"🟢 从目标图像匹配中初始化")
            bbox = self.match_target_image(frame,self.target_img_path)
            if bbox:
                print(f"匹配成功 bbox: {bbox}")
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[0]+bbox[2], bbox[1]+bbox[3]), (0,255,0), 2)
                # cv2.imshow("Template Match", frame)
                # cv2.waitKey(1000)
                # cv2.destroyWindow("Template Match")
        # Case4: 特征匹配
        elif feature_match:
            print("🟢 尝试使用 ORB 特征匹配初始化...")
            template = cv2.imread(self.target_img_path)
            if template is not None:
                bbox = self.orb_match_bbox(frame, template)
                if bbox:
                    print(f"匹配成功 bbox: {bbox}")
                    cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[0] + bbox[2], bbox[1] + bbox[3]), (255, 128, 0), 2)
                    # cv2.imshow("ORB Match", frame)
                    # cv2.waitKey(1000)
                    # cv2.destroyWindow("ORB Match")
        if not bbox or bbox[2] == 0 or bbox[3] == 0:
            print("❌ 未能获取有效目标框")
            exit()

        self.bbox = bbox
        self.tracker = DETECTOR_SET[self.model]  # 每次重新初始化 tracker
        self.tracker.init(frame, bbox)

        if save_bbox:
            self.save_bbox()
            self.save_template(frame, bbox, save_path=self.target_img_path)

        print("✅ Tracker 初始化完成")

    def detect(self, frame, reinit_on_lost=True):
        success, box = self.tracker.update(frame)
        if success:
            self.bbox = box
            center = self.get_box_center(box)
            cv2.rectangle(frame, (int(box[0]), int(box[1])),
                          (int(box[0] + box[2]), int(box[1] + box[3])),
                          (0, 255, 0), 2)
            cv2.putText(frame, f"Tracking {center}", (int(box[0]), int(box[1]) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            return frame, box, center

        else:
            cv2.putText(frame, "Tracking Lost", (50, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
            print("⚠️ 目标丢失！")

            if reinit_on_lost:
                print("🔁 自动重新初始化...")
                self.init_detector(manual=True)  # 你也可以改为 target_img_path 模式
            return frame, None, None

    def get_box_center(self, box):
        x, y, w, h = box
        return (x + w // 2, y + h // 2)

    def exit(self):
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    detector = NormalDetector()
    detector.init_detector()

    while True:
        ret, frame = detector.cap.read()
        if not ret:
            print("摄像头读取失败")
            break

        frame, box, center = detector.detect(frame)
        cv2.imshow("Normal Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    detector.exit()