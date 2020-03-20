import numpy as np
import robosuite.utils.transform_utils as trans
import scipy.linalg


def nullspace_torques(mass_matrix, nullspace_matrix, initial_joint, joint_pos, joint_vel):
    joint_kp = 10
    joint_kv = np.sqrt(joint_kp) * 2
    pose_torques = np.dot(mass_matrix, (joint_kp * (
            initial_joint - joint_pos) - joint_kv * joint_vel))
    nullspace_torques = np.dot(nullspace_matrix.transpose(), pose_torques)
    return nullspace_torques


def opspace_matrices(mass_matrix, J_full, J_pos, J_ori):
    mass_matrix_inv = scipy.linalg.inv(mass_matrix)

    # J M^-1 J^T
    lambda_full_inv = np.dot(
        np.dot(J_full, mass_matrix_inv),
        J_full.transpose())

    # (J M^-1 J^T)^-1
    lambda_full = scipy.linalg.inv(lambda_full_inv)

    # Jx M^-1 Jx^T
    lambda_pos_inv = np.dot(
        np.dot(J_pos, mass_matrix_inv),
        J_pos.transpose())

    # Jr M^-1 Jr^T
    lambda_ori_inv = np.dot(
        np.dot(J_ori, mass_matrix_inv),
        J_ori.transpose())

    # take the inverse, but zero out elements in cases of a singularity
    # todo: maybe there is an error here? check with danfei and ajay
    svd_u, svd_s, svd_v = np.linalg.svd(lambda_pos_inv)
    singularity_threshold = 0.00025
    svd_s_inv = [0 if x < singularity_threshold else 1. / x for x in svd_s]
    lambda_pos = svd_v.T.dot(np.diag(svd_s_inv)).dot(svd_u.T)

    svd_u, svd_s, svd_v = np.linalg.svd(lambda_ori_inv)
    svd_s_inv = [0 if x < singularity_threshold else 1. / x for x in svd_s]
    lambda_ori = svd_v.T.dot(np.diag(svd_s_inv)).dot(svd_u.T)

    # nullspace
    Jbar = np.dot(mass_matrix_inv, J_full.transpose()).dot(lambda_full)
    nullspace_matrix = np.eye(J_full.shape[-1], J_full.shape[-1]) - np.dot(Jbar, J_full)

    return lambda_full, lambda_pos, lambda_ori, nullspace_matrix


def orientation_error(desired, current):
    """
    Optimized function to determine orientation error from matrices
    """

    def cross_product(vec1, vec2):
        mat = np.array(([0, -vec1[2], vec1[1]],
                        [vec1[2], 0, -vec1[0]],
                        [-vec1[1], vec1[0], 0]))
        return np.dot(mat, vec2)

    rc1 = current[0:3, 0]
    rc2 = current[0:3, 1]
    rc3 = current[0:3, 2]
    rd1 = desired[0:3, 0]
    rd2 = desired[0:3, 1]
    rd3 = desired[0:3, 2]

    error = 0.5 * (cross_product(rc1, rd1) + cross_product(rc2, rd2) + cross_product(rc3, rd3))

    return error


def set_goal_position(delta,
                      current_position,
                      position_limit=None,
                      set_pos=None):
    """
    Calculates and returns the desired goal position, clipping the result accordingly to @position_limits.
    @delta and @current_position must be specified if a relative goal is requested, else @set_pos must be
    specified to define a global goal position
    """
    n = len(current_position)
    if set_pos is not None:
        goal_position = set_pos
    else:
        goal_position = current_position + delta

    if position_limit is not None:
        if position_limit.shape != (2,n):
            raise ValueError("Position limit should be shaped (2,{}) "
                             "but is instead: {}".format(n, position_limit.shape))

        # Clip goal position
        goal_position = np.clip(goal_position, position_limit[0], position_limit[1])

    return goal_position


def set_goal_orientation(delta,
                         current_orientation,
                         orientation_limit=None,
                         set_ori=None):
    """
    Calculates and returns the desired goal orientation, clipping the result accordingly to @orientation_limits.
    @delta and @current_orientation must be specified if a relative goal is requested, else @set_ori must be
    specified to define a global orientation position
    """
    # directly set orientation
    if set_ori is not None:
        goal_orientation = set_ori

    # otherwise use delta to set goal orientation
    else:
        rotation_mat_error = trans.euler2mat(-delta)
        goal_orientation = np.dot(rotation_mat_error.T, current_orientation)

    #check for orientation limits
    if np.array(orientation_limit).any():
        if orientation_limit.shape != (2,3):
            raise ValueError("Orientation limit should be shaped (2,3) "
                             "but is instead: {}".format(orientation_limit.shape))
        # TODO: Limit rotation!
        euler = trans.mat2euler(goal_orientation)

        limited = False
        for idx in range(3):
            if orientation_limit[0][idx] < orientation_limit[1][idx]:  # Normal angle sector meaning
                if orientation_limit[0][idx] < euler[idx] < orientation_limit[1][idx]:
                    continue
                else:
                    limited = True
                    dist_to_lower = euler[idx] - orientation_limit[0][idx]
                    if dist_to_lower > np.pi:
                        dist_to_lower -= 2 * np.pi
                    elif dist_to_lower < -np.pi:
                        dist_to_lower += 2 * np.pi

                    dist_to_higher = euler[idx] - orientation_limit[1][idx]
                    if dist_to_lower > np.pi:
                        dist_to_higher -= 2 * np.pi
                    elif dist_to_lower < -np.pi:
                        dist_to_higher += 2 * np.pi

                    if dist_to_lower < dist_to_higher:
                        euler[idx] = orientation_limit[0][idx]
                    else:
                        euler[idx] = orientation_limit[1][idx]
            else:  # Inverted angle sector meaning
                if (orientation_limit[0][idx] < euler[idx]
                        or euler[idx] < orientation_limit[1][idx]):
                    continue
                else:
                    limited = True
                    dist_to_lower = euler[idx] - orientation_limit[0][idx]
                    if dist_to_lower > np.pi:
                        dist_to_lower -= 2 * np.pi
                    elif dist_to_lower < -np.pi:
                        dist_to_lower += 2 * np.pi

                    dist_to_higher = euler[idx] - orientation_limit[1][idx]
                    if dist_to_lower > np.pi:
                        dist_to_higher -= 2 * np.pi
                    elif dist_to_lower < -np.pi:
                        dist_to_higher += 2 * np.pi

                    if dist_to_lower < dist_to_higher:
                        euler[idx] = orientation_limit[0][idx]
                    else:
                        euler[idx] = orientation_limit[1][idx]
        if limited:
            goal_orientation = trans.euler2mat(np.array([euler[1], euler[0], euler[2]]))
    return goal_orientation