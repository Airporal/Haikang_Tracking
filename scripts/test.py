import numpy as np

class ExtrinsicTest:
    def __init__(self):
        # 构造一个仿射矩阵 (平移+缩放+旋转)
        theta = np.radians(15)  # 旋转 15°
        scale = 1.2
        tx, ty = 100, 50  # 平移

        affine = np.array([
            [scale*np.cos(theta), -scale*np.sin(theta), tx, 0],
            [scale*np.sin(theta),  scale*np.cos(theta), ty, 0],
            [0, 0, 1, 0]
        ])
        self.extrinsic = np.vstack((affine, [0,0,0,1]))

    def apply_affine_transform(self, points):
        """像素→世界"""
        A = np.hstack((points, np.ones((points.shape[0], 2))))  # (N,4)
        detect_points = np.dot(A, self.extrinsic.T)
        mapped_points = detect_points[:, :2]
        return mapped_points

    def world_to_pixel(self, world_points):
        """世界→像素（反变换）"""
        A = np.hstack((world_points, np.ones((world_points.shape[0], 2))))  # (N,4)
        detect_points = np.dot(A, np.linalg.inv(self.extrinsic).T)
        mapped_points = detect_points[:, :2]
        return mapped_points

def test_accuracy():
    tester = ExtrinsicTest()

    # 1. 生成随机像素点
    pixel_points = np.random.randint(0, 500, size=(10, 2))  # (10,2)
    print("原始像素点:\n", pixel_points)

    # 2. 像素→世界
    world_points = tester.apply_affine_transform(pixel_points)
    print("转换后的世界点:\n", world_points)

    # 3. 世界→像素
    recon_pixels = tester.world_to_pixel(world_points)
    print("还原的像素点:\n", recon_pixels)

    # 4. 计算误差
    error = np.linalg.norm(pixel_points - recon_pixels, axis=1)
    print("每个点的误差:\n", error)
    print("最大误差:", np.max(error))

if __name__ == "__main__":
    test_accuracy()
