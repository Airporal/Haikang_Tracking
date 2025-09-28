import numpy as np
import time
import functools
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import CONFIG_DIR

def projection_on_plane_with_origin(P, A, B, C, D, origin=(1, 1, 1)):
    """
    将点P投影到平面Ax + By + Cz + D = 0上，且以(1, 1, 1)为平面坐标系的原点。
    
    P: 需要投影的点 (n, 3)
    A, B, C, D: 平面方程的系数 Ax + By + Cz + D = 0
    origin: 平面坐标系的原点 (默认(1, 1, 1))
    """
    # 平面法向量
    normal_vector = np.array([A, B, C])
    normal_unit_vector = normal_vector / np.linalg.norm(normal_vector)

    # 计算原点到平面的距离（平面到原点的距离）
    P_centered = P - origin  # 平移，使得原点为origin
    
    # 计算点P在法向量方向上的投影
    distance = np.dot(P_centered, normal_unit_vector)
    
    # 计算投影点
    P_projected = P - distance[:, None] * normal_unit_vector  # 投影点

    return P_projected

def calculate_normal(points):
    v1 = points[3] - points[0]
    v2 = points[2] - points[0]
    normal = np.cross(v1, v2)
    return normal


def fit_plane_least_squares(points):
    """
    使用最小二乘法拟合平面
    points: 3D点集 (n, 3)，每个点为 (x, y, z)
    返回平面方程的系数 (A, B, C, D)
    """
    # 准备数据
    # points是n x 3 的矩阵，每行是一个三维点 (x, y, z)
    A = np.c_[points[:, 0], points[:, 1], np.ones(points.shape[0])]  # x, y, 1
    B = points[:, 2]  # z (目标变量)
    
    # 使用最小二乘法求解 (A, B, C)
    # Ax = B -> 求解x
    # 使用np.linalg.lstsq来解最小二乘问题
    coeffs, resids, rank, s = np.linalg.lstsq(A, B, rcond=None)
    
    # coeffs[0]是A, coeffs[1]是B, coeffs[2]是C
    A, B, C = coeffs
    D = -1  # 由于右侧是z = Ax + By + C, 这里假定D= -1 来标准化
    return A, B, C, D


def show_2D(projected_points,win_name='Projected Points on Plane'):
    plt.ion()
    plt.figure()
    colors = ['red', 'blue', 'green', 'orange']
    plt.scatter(projected_points[:, 0], projected_points[:, 1], color=colors, label='Projected Points')

    ## 设置坐标轴标签
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.axis('equal')
    plt.title(win_name)

    ## 显示图例
    plt.legend()
    plt.show(block=True)

def get_2D_plane_pos(points,use_ABCD=True,draw_flag=False):
    """
        得到点的平面坐标
    """
    fit_plane_data = os.path.join(CONFIG_DIR,'fit_plane_data.npz')
    if use_ABCD==True:
        type='dst'
        fit_plane_data = np.load(fit_plane_data)
        A = fit_plane_data['A']
        B = fit_plane_data['B']
        C = fit_plane_data['C']
        D = fit_plane_data['D']
    elif use_ABCD==False:
        type='src'
        A, B, C, D = fit_plane_least_squares(points)
        np.savez(fit_plane_data, A=A, B=B, C=C, D=D)
    # 将点投影到平面
    origin = np.array([0, 0, 0])
    projected_points = projection_on_plane_with_origin(points, A, B, C, D, origin)

    # 绘制投影点
    if draw_flag:
        show_2D(projected_points,win_name = 'Projected Points on Plane'+f"({type})")

    return projected_points[:, :2]

def show_3D(points):
    normal = calculate_normal(points)

    ## 使用法向量和平面上的一点来确定D
    A, B, C = normal
    D = -np.dot(normal, points[0])

    ## 生成平面上的点
    xx, yy = np.meshgrid(range(int(np.min(points))+5, int(np.max(points))+5), 
                         range(int(np.min(points))+5, int(np.max(points))+5))
    xx, yy = np.meshgrid(range(-2, 2), range(-2, 2))    
    zz = (-A * xx - B * yy - D) / C

    ## 绘制平面和点
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    # 绘制平面
    ax.plot_surface(xx, yy, zz, alpha=0.5)
    # 绘制点
    colors = ['red', 'blue', 'green', 'orange']
    ax.scatter(points[:, 0], points[:, 1], points[:, 2], color=colors)
    # 设置坐标轴标签
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.axis('equal')
    plt.xlim(np.min(points[:, 0])-0.5, np.max(points[:, 0])+0.5)  # X轴范围从0到12
    plt.ylim(np.min(points[:, 1])-0.5, np.max(points[:, 1])+0.5)  # Y轴范围从0到12   
    plt.show(block=True)

def save_intrinsic(camera_matrix,dist_coeffs):
    np.savez_compressed("camera_calibration.npz",camera_matrix=camera_matrix,dist_coeffs=dist_coeffs)
    print("Save intrinsic successfully!")
    print(f"camera_matrix{camera_matrix.shape}:\n{camera_matrix}")
    print(f"dist_coeffs{dist_coeffs.shape}:\n{dist_coeffs}")
    
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

def stopwatch(func):
    """装饰器：计算函数运行时间"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"函数 {func.__name__} 耗时 {end - start:.6f} 秒")
        return result
    return wrapper

if __name__ == '__main__':
    #  更新相机内参
    camera_calibration = os.path.join(CONFIG_DIR,'camera_calibration.npz')
    camera_matrix = np.load(camera_calibration)
    print(f"camera_matrix{camera_matrix['camera_matrix'].shape}:\n{camera_matrix['camera_matrix']}")
    print(f"dist_coeffs{camera_matrix['dist_coeffs'].shape}:\n{camera_matrix['dist_coeffs']}")
    # 2.460021436571527e+03   2459.86675392013
    # new_intrinsics = np.array([
    #     [1.228164273e+03,0,1.818223525286718e+03],
    #     [0,1.229066895e+03,1.118212676244958e+03],
    #     [0,0,1]
    # ])
    new_intrinsics = np.array([
        [2.460021436571527e+03,0,1.818223525286718e+03],
        [0,2.459866753920130e+03,1.118212676244958e+03],
        [0,0,1]
    ])
    # k1,k2,p1,p2,k3
    # new_dist_coeffs = np.array([-0.134992249, 0.091937196, 0.000667906,-0.000938182, 0.393600290]).reshape(1,5)
    new_dist_coeffs = np.array([-0.127987199366883, 0.140608427063986, 0,0, -0.084867565270828]).reshape(1,5)

    save_intrinsic(new_intrinsics,new_dist_coeffs)