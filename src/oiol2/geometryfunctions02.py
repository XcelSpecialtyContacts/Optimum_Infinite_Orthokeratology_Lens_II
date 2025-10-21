# geometryfunctions02.py
#
# this houses all the geometry functions used in constructing a lens
# surface
#
# I'm using this specifically for the SCone evaluation project
#
# Date: 2024-03-19
# By: AG
#
#

import math
import json
import numpy as np
import sympy as sp
from scipy.interpolate import interp1d
from scipy.interpolate import CubicSpline
from scipy.interpolate import BarycentricInterpolator
from scipy.interpolate import make_interp_spline
from scipy.interpolate import CubicHermiteSpline
from scipy.interpolate import UnivariateSpline
from scipy.optimize import root_scalar
from scipy.optimize import fsolve


def sphereSAG(radius, cordLength):
    # This calculates the sagital depth of an arc given the radius and
    # the cord length
    return radius - (((radius**2) - ((cordLength / 2) ** 2))) ** (1 / 2)


def circleFromThreePoints(xI, yI, xj, yj, xk, yk):
    # This function will calculate the center coordinates of a circle
    # and the radius intersecting three point
    # returns the radius, and the center point

    a = (-1 * (xI**2)) / (-2 * yI + 2 * yj)
    b = ((xj**2)) / (-2 * yI + 2 * yj)
    d = (-1 * (yI**2)) / (-2 * yI + 2 * yj)
    E = ((yj**2)) / (-2 * yI + 2 * yj)
    F = (2 * xI - 2 * xj) / (-2 * yI + 2 * yj)
    G = (-1 * (xj**2)) / (-2 * xj + 2 * xk)
    h = ((xk**2)) / (-2 * xj + 2 * xk)
    i = (-1 * (yj**2)) / (-2 * xj + 2 * xk)
    j = ((yk**2)) / (-2 * xj + 2 * xk)
    K = (2 * yj - 2 * yk) / (-2 * xj + 2 * xk)
    xC = (G + h + i + j + K * a + K * b + K * d + K * E) / (1 - K * F)
    yC = a + b + d + E + F * xC
    r = ((((xI - xC) ** 2) + ((yI - yC) ** 2))) ** (1 / 2)
    return r, xC, yC


def yValOnCircle(r, x, cx, cy):
    # calculates the y component on a circle given the x component the
    # radius, and the center point

    y1 = cy - (r**2 - (x - cx) ** 2) ** (1 / 2)
    y2 = cy + (r**2 - (x - cx) ** 2) ** (1 / 2)

    return [y1, y2]


def xValOnCircle(r, y, cx, cy):
    # calculates the y component on a circle given the x component the
    # radius, and the center point

    x1 = cx - (r**2 - (y - cy) ** 2) ** (1 / 2)
    x2 = cx + (r**2 - (y - cy) ** 2) ** (1 / 2)

    return [x1, x2]


def CentersFrom2PtsAndR(xI, yI, xII, yII, r):
    # calculate the x coordanate value for the center of a circle
    # constrained by 2 points in a plane and the radius of the circle.

    q = ((xII - xI) ** 2 + (yII - yI) ** 2) ** (1 / 2)
    x3 = (xI + xII) / 2
    y3 = (yI + yII) / 2

    basex = ((r**2 - (q / 2) ** 2) ** (1 / 2)) * (yI - yII) / q
    basey = ((r**2 - (q / 2) ** 2) ** (1 / 2)) * (xII - xI) / q

    cx1 = x3 + basex
    cy1 = y3 + basey
    cx2 = x3 - basex
    cy2 = y3 - basey

    return [cx1, cy1, cx2, cy2]


def BackVertexPower(BCR, FCR, RIM, CT):
    # This calculates the Back Vertex Power in diopters given the base
    # curve radius (BCR) in mm, the front curve radius (FCR) in mm, the
    # refactive index of the lens material (RIM), and the center
    # thickness of the lens (CT) in mm.
    RIA = 1  # refactive index of air
    k = 0.001  # units factor
    FCD = (RIM - RIA) / (FCR * k)  # Front Curve in diopters
    BCD = (RIA - RIM) / (BCR * k)  # Base Curve in diopters
    return FCD / (1 - (CT * k / RIM) * FCD) + BCD


def FCRFromBVP(BVP, BCR, RIM, CT):
    # This calculates the Front Curve Radius in mm given the Back Vertex
    # Power (BVP) in diopters, the base curve radius (BCR) in mm, the
    # refactive index of the lens material (RIM), and the center
    # thickness of the lens (CT) in mm.
    RIA = 1  # refactive index of air
    k = 0.001  # units factor
    BCD = (RIA - RIM) / (BCR * k)  # Base Curve in diopters
    FCD = (RIM * (BVP - BCD)) / (
        RIM - BCD * CT * k + BVP * CT * k
    )  # Front Curve in diopters
    return (RIM - RIA) / (FCD * k)


def FrontVertexPower(BCR, FCR, RIM, CT):
    # This calculates the Front Vertex Power in diopters given the base
    # curve radius (BCR) in mm, the front curve radius (FCR) in mm, the
    # refactive index of the lens material (RIM), and the center
    # thickness of the lens (CT) in mm.
    RIA = 1  # refactive index of air
    k = 0.001  # units factor
    FCD = (RIM - RIA) / (FCR * k)  # Front Curve in diopters
    BCD = (RIA - RIM) / (BCR * k)  # Base Curve in diopters
    return BCD / (1 - (CT * k / RIM) * BCD) + FCD


def FCRFromFVP(FVP, BCR, RIM, CT):
    # This calculates the Front Curve Radius in mm given the Front
    # Vertex Power (FVP) in diopters, the base curve radius (BCR) in mm,
    # the refactive index of the lens material (RIM), and the center
    # thickness of the lens (CT) in mm.
    RIA = 1  # refactive index of air
    k = 0.001  # units factor
    BCD = (RIA - RIM) / (BCR * k)  # Base Curve in diopters
    FCD = FVP - BCD / (1 - (CT * k / RIM) * BCD)  # Front Curve in diopters
    return (RIM - RIA) / (FCD * k)


def DiopterToMM(x):
    # this converts a radius of curvature in diopters
    # to mm
    return 337.5 / x


def MMToDiopter(x):
    # this converts a radius of curvature in mm
    # to diopters
    return 337.5 / x


def CenterOfCurveTangentToCurve(RI, RII, x, y):
    """
    This function will calculate the centerpoint of a circle given when
    it is tangent to a a circle.
    RI: radius of first circle
    RII: radius of the circle that the center is being calculated
    x: x value of the point at which the two circles are tangent
    y: y value of the point at which the two circles are tangent

    WARNING WARNING WARNING WARNING
    I wrote this to calculate the center of a curve for an anlysis
    of the eJupiter lens.  I don't believe I have completely thought
    this out so as to make it applicable for all cases.  So if you
    use it double check that it is giving you what you expect.
    """
    theta = math.acos(x / RI)
    m1 = -math.cos(theta) / math.sin(theta)
    m2 = -1 / m1
    b2 = y - x * m2
    cx1 = x - math.sqrt(RII**2 / (1 + m2**2))
    cy1 = cx1 * m2 + b2
    cx2 = x + math.sqrt(RII**2 / (1 + m2**2))
    cy2 = cx2 * m2 + b2
    return [cx1, cy1, cx2, cy2]


# Calculate conic constant (K) frome eccentricity (e)
def calc_K_from_e(e_val):
    return -1 * e_val**2


# The equation for a conic
def conic(x, R_0, K, direction):
    # R: radius of curvature at apex
    # K: conic constant
    # K > 0, oblate ellipse
    # K = 0, circle
    # -1 < K < 0, prolate ellipse
    # K = -1, parabola
    # K < -1, hyperbola
    R_0 = float(R_0)
    K = float(K)
    if direction == "convex":
        return -1 * (x**2 / (R_0 + np.sqrt(R_0**2 - (K + 1) * x**2)))
    else:
        return x**2 / (R_0 + np.sqrt(R_0**2 - (K + 1) * x**2))


def derivative_conic(x, R_0, K, direction):
    # this is the first derivative of the conic curve equation
    # this is useful in calculating the slope of a line tangent at a point on the line
    R_0 = float(R_0)
    K = float(K)
    if direction == "convex":
        numerator = -2 * x * (R_0 + np.sqrt(R_0**2 - (K + 1) * x**2))
    else:
        numerator = -2 * x * (R_0 + np.sqrt(R_0**2 - (K + 1) * x**2))
    denominator = (R_0 + np.sqrt(R_0**2 - (K + 1) * x**2)) ** 2
    return numerator / denominator


def offset_conic(x, R_0, K, offset, direction):
    R_0 = float(R_0)
    K = float(K)
    dy_dx = derivative_conic(x, R_0, K, direction)
    nx = -dy_dx
    ny = 1
    norm = np.sqrt(nx**2 + ny**2)
    nx, ny = nx / norm, ny / norm
    return conic(x, R_0, K, direction) - ny * offset


def curvetype(K):
    # K: conic constant
    if K > 0:
        return "oblate ellipse"
    elif K == 0:
        return "circle"
    elif K > -1 and K < 0:
        return "prolate ellipse"
    elif K == -1:
        return "parabola"
    elif K < -1:
        return "hyperbola"
    # If an exact match is not confirmed, this last case will be used if provided
    else:
        return "Something's wrong with curve type identification"


# The equation for a line
def line(x, m, b):
    # m: slope
    # b: y-axis intercept
    return m * x + b


# The y-intercept of a line
def y_intercept(x_val, y_val, m_val):
    # (x_val, y_val): point on the line
    # m_val: slope
    return y_val - m_val * x_val


# Calculate the slope and angle of a line tangent to a conic curve at a given point.
def slope_and_angle_of_line_tangent_to_curve(x_val, R_val, K_val):

    # Define symbols
    x, R, K = sp.symbols("x R K")

    # Define the equation
    y = x**2 / (R + sp.sqrt(R**2 - (K + 1) * x**2))

    # First derivative with respect to x
    y_prime = sp.diff(y, x)

    # Slope of a tangent line at point x_val
    slope_of_line = y_prime.subs({x: x_val, R: R_val, K: K_val})

    # Calculate the angle of the tangent line
    angle_radians = sp.atan(slope_of_line)
    angle_degrees = sp.deg(angle_radians)

    return slope_of_line, angle_radians, angle_degrees


# Calculate the radius of curvature at a point on the curve.
def radius_of_curvature(x_val, R_val, K_val):
    if curvetype(K_val) == "circle":
        rho_val = R_val
    else:
        # Define symbols
        x, R, K = sp.symbols("x R K")

        # Define the equation
        y = x**2 / (R + sp.sqrt(R**2 - (K + 1) * x**2))

        # First derivative with respect to x
        y_prime = sp.diff(y, x)

        # Second derivative with respect to x
        y_double_prime = sp.diff(y_prime, x)

        # Radius of curvature formula
        rho = (1 + y_prime**2) ** (3 / 2) / sp.Abs(y_double_prime)

        # Substitute the given values and evaluate
        rho_val = rho.subs({x: x_val, R: R_val, K: K_val}).evalf()

    return rho_val


def sagitta(radius, iHalfCordLength, oHalfCordLength):
    # This calculates the sagital depth of an arc given the radius and
    # the cord length
    iCordLength = 2 * iHalfCordLength
    oCordLength = 2 * oHalfCordLength
    return (radius - math.sqrt(((radius**2) - ((oCordLength / 2) ** 2)))) - (
        radius - math.sqrt(((radius**2) - ((iCordLength / 2) ** 2)))
    )


# Distance between two points
def distance_between_points(p1, p2):
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def distance_along_line(slope, y_intercept, x1, x2):
    # Calculate the distance along a line given
    # y_intercept: the y intercept for the line
    # x1: the starting x value
    # x2: the ending x value
    y1 = slope * x1 + y_intercept
    y2 = slope * x2 + y_intercept

    # Calculate the distance using the distance formula
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    return distance


def point_along_line(slope, y_intercept, distance, x_direction, x_start):
    """
    Computes the x, y values for a point along a line given the slope, y-intercept,
    distance, x direction to move, and starting x value.

    Args:
        slope (float): Slope of the line.
        y_intercept (float): Y-intercept of the line.
        distance (float): Distance to move along the line.
        x_direction (int): Direction to move (1 for positive x, -1 for negative x).
        x_start (float): Starting x value on the line.

    Returns:
        float: The x value of the point after moving the specified distance.
        float: The y value of the point after moving the specified distance.
    """
    # Calculate the change in x based on the distance and direction
    delta_x = distance / math.sqrt(1 + slope**2) * x_direction

    # Calculate the new x and y values
    x_new = x_start + delta_x
    y_new = slope * x_new + y_intercept

    return x_new, y_new


# Determine if a curve is concave or convex
def curve_direction(y_val):
    if y_val < 0:  # curve is convex
        return "convex"
    else:
        return "concave"


# Calculate K
def calc_K(x_val, y_val, R_val):
    # this returns the value for the conic constant given a R0 for the curve
    # and the ending point x_val, y_val.
    if y_val < 0:  # curve is convex
        return (R_val**2 - ((x_val**2) / (-1 * y_val) - R_val) ** 2) / (x_val**2) - 1
    else:  # curve is concave
        return (R_val**2 - ((x_val**2) / y_val - R_val) ** 2) / (x_val**2) - 1


# Function to find the index of the closest point
# This function is needed to shorten the list of points for a given zone
def find_closest_index(x_list, y_list, point):
    distances = [
        (x - point[0]) ** 2 + (y - point[1]) ** 2 for x, y in zip(x_list, y_list)
    ]
    return np.argmin(distances)


# This takes a point in the Global Coordinate System (GCS) and then translates it to the
# Alternate Coordinate System (ACS)
def translate_to_ACS(point, origin, theta):
    """
    point: The (x, y) value in the GCS
    origin: The (x, y) value of the ACS Origin in the GCS
    theta: Rotation angle of the ACS relative to the GCS
    """
    # Unpack the point and origin
    x, y = point
    x0, y0 = origin

    # Ensure theta is a numerical value if it's symbolic
    theta_num = float(theta.evalf()) if hasattr(theta, "evalf") else theta

    # Translate the point to the ACS origin
    x_translated = x - x0
    y_translated = y - y0

    # Rotate the point to align with the ACS orientation
    rotation_matrix = np.array(
        [
            [np.cos(-theta_num), -np.sin(-theta_num)],
            [np.sin(-theta_num), np.cos(-theta_num)],
        ]
    )
    x_acs, y_acs = np.dot(rotation_matrix, [x_translated, y_translated])

    return x_acs, y_acs


# This takes a point in the Alternate Coordinate System (ACS) and then translates it to the
# Global Coordinate System (GCS)
def translate_to_GCS(point_acs, origin, theta):
    """
    point_acs: The (x, y) value in the ACS
    origin: The (x, y) value of the ACS Origin in the GCS
    theta: Rotation angle of the ACS relative to the GCS
    """

    # Ensure theta is a numerical value if it's symbolic
    theta_num = float(theta.evalf()) if hasattr(theta, "evalf") else theta

    # Apply the inverse rotation
    rotation_matrix_inv = np.array(
        [
            [np.cos(theta_num), -np.sin(theta_num)],
            [np.sin(theta_num), np.cos(theta_num)],
        ]
    )
    x_acs, y_acs = point_acs
    x_translated, y_translated = np.dot(rotation_matrix_inv, [x_acs, y_acs])

    # Translate back to the GCS
    x0, y0 = origin
    x_gcs = x_translated + x0
    y_gcs = y_translated + y0

    return x_gcs, y_gcs


def calc_junction_thickness(
    Power,
    Base_radius,
    RI,
    Center_Thickness,
    Front_Optic_Dia,
    origin_BCCS,
    angle_BCCS,
    BC_meridian_x,
    BC_meridian_y,
):
    Power = float(Power)
    Base_radius = float(Base_radius)
    RI = float(RI)
    Center_Thickness = float(Center_Thickness)
    Front_Optic_Dia = float(Front_Optic_Dia)
    angle_BCCS = float(angle_BCCS)
    FC_K = 0.0  # sphere

    FC_radius_FV = float(FCRFromFVP(Power, Base_radius, RI, Center_Thickness))

    # Calculate the resulting junction thickness
    FC_origin_GCS = (float(origin_BCCS[0]), -Center_Thickness)
    angle_FC = angle_BCCS
    FC_sag = float(
        sagitta(FC_radius_FV, 0, Front_Optic_Dia / 2)
    )  # Saggital depth of the FC zone
    FC_end_point_FCCS = (Front_Optic_Dia / 2, FC_sag)
    FC_x_FCCS = np.linspace(0, FC_end_point_FCCS[0], 100)
    FC_y_FCCS = conic(FC_x_FCCS, FC_radius_FV, FC_K, "concave")
    FC_points_FCCS = zip(FC_x_FCCS, FC_y_FCCS)

    FC_x_GCS, FC_y_GCS = [], []
    for point_acs in FC_points_FCCS:
        point_gcs = translate_to_GCS(point_acs, FC_origin_GCS, angle_FC)
        FC_x_GCS.append(float(point_gcs[0]))
        FC_y_GCS.append(float(point_gcs[1]))

    M_tangent_line_at_end_point_FCCS, _, _ = slope_and_angle_of_line_tangent_to_curve(
        FC_x_FCCS[-1], FC_radius_FV, FC_K
    )
    M_normal_line_at_end_point_FCCS = float(-1 / M_tangent_line_at_end_point_FCCS)
    B_normal_line_at_end_point_FCCS = float(
        y_intercept(
            FC_end_point_FCCS[0], FC_end_point_FCCS[1], M_normal_line_at_end_point_FCCS
        )
    )

    point1_on_line_GCS = translate_to_GCS(
        (0, B_normal_line_at_end_point_FCCS), FC_origin_GCS, angle_FC
    )
    point2_on_line_GCS = translate_to_GCS(FC_end_point_FCCS, FC_origin_GCS, angle_FC)

    M_normal_line_at_end_point_GCS = float(
        (point2_on_line_GCS[1] - point1_on_line_GCS[1])
        / (point2_on_line_GCS[0] - point1_on_line_GCS[0])
    )
    B_normal_line_at_end_point_GCS = float(
        y_intercept(
            point2_on_line_GCS[0], point2_on_line_GCS[1], M_normal_line_at_end_point_GCS
        )
    )

    # Interpolate the curve
    curve_interp = interp1d(BC_meridian_x, BC_meridian_y, kind="linear")

    # Define the line function
    def line_func(x):
        return M_normal_line_at_end_point_GCS * x + B_normal_line_at_end_point_GCS

    # Define a function for the difference between the curve and the line
    def diff_func(x):
        return curve_interp(x) - line_func(x)

    x_guess = BC_meridian_x[0]  # Adjust as needed
    result = root_scalar(
        diff_func, bracket=[BC_meridian_x.min(), BC_meridian_x.max()], x0=x_guess
    )

    if result.converged:
        x_intersect = result.root
        y_intersect = line_func(x_intersect)
        calc_jt = float(
            distance_between_points(
                (x_intersect, y_intersect), (FC_x_GCS[-1], FC_y_GCS[-1])
            )
        )
    else:
        print("Intersection not found within the given range.")
        calc_jt = None  # or appropriate error handling

    return calc_jt, FC_x_GCS, FC_y_GCS


def calculate_arc_angle_diff(C, S, E, R):
    # This calculates the angle between the starting and ending points
    # Convert points to numpy arrays for vector calculations
    C = np.array(C)
    S = np.array(S)
    E = np.array(E)

    # Calculate vectors CS and CE
    CS = S - C
    CE = E - C

    # Calculate dot product of CS and CE
    dot_product = np.dot(CS, CE)

    # Calculate angle in radians
    angle_rad = np.arccos(dot_product / (R**2))

    # Convert angle to degrees for readability (optional)
    angle_deg = np.degrees(angle_rad)

    return angle_rad, angle_deg


def calculate_arc_angles(C, S, E):
    # This calculates the angles of points relative to the positive x-axis
    # The positive x-axis is 0 radians or 0 degrees
    # Calculate starting angle
    theta_start = np.arctan2(S[1] - C[1], S[0] - C[0])

    # Calculate ending angle
    theta_end = np.arctan2(E[1] - C[1], E[0] - C[0])

    # Ensure angles are positive, and convert to degrees
    theta_start_deg = np.degrees(theta_start) % 360
    theta_end_deg = np.degrees(theta_end) % 360

    # Return results in radians and degrees
    return (theta_start, theta_end), (theta_start_deg, theta_end_deg)


# Calculate the slope of a line created by joining 2 points
def slope_from_2_points(P1, P2):
    # Extract coordinates from the points
    x1, y1 = P1
    x2, y2 = P2

    # Calculate the slope
    try:
        slope = (y2 - y1) / (x2 - x1)
        return slope
    except ZeroDivisionError:
        return "Undefined"  # This occurs when x2 = x1, vertical line


def slope_and_intercept_from_2_points(P1, P2):
    # Extract coordinates from the points
    x1, y1 = P1
    x2, y2 = P2

    # Calculate the slope
    try:
        slope = (y2 - y1) / (x2 - x1)
        # Calculate the y-intercept using the formula: y = mx + b => b = y - mx
        y_intercept = y1 - slope * x1
        return slope, y_intercept
    except ZeroDivisionError:
        return "Undefined", None  # This occurs when x2 = x1, vertical line


def tangent_slope_at_x(x, y, x_target):
    """
    Calculate the slope of the tangent to the curve at a specific x value.

    Parameters:
    x (numpy.ndarray): The x values of the curve.
    y (numpy.ndarray): The y values of the curve.
    x_target (float): The x value where to calculate the tangent slope.

    Returns:
    float: The slope of the tangent line at x_target.
    """
    # Ensure x and y are numpy arrays
    x = np.array(x)
    y = np.array(y)

    # Use UnivariateSpline to fit a spline to the data
    # s=0 ensures it passes through all points for an interpolating spline
    spline = UnivariateSpline(x, y, s=0)

    # Get the first derivative of the spline, which represents the slope
    dydx = spline.derivative()

    # Evaluate the derivative at x_target to get the slope of the tangent line
    slope_at_x_target = dydx(x_target)

    return slope_at_x_target


# edge_radius_center(PC02_x_PC02CS[0], PC02_x_PC02CS[-1], PC02_R0, PC02_K, M_EB_PC02CS, B_EB_PC02CS, Edge_radius, direction)
# Calculate the center of the edge radius
def edge_radius_center(x_i, x_f, R, K, m, b, r, direction):
    # This function should be used in the CS of the curve tangent to the edge radius
    x_i = float(x_i)  # the beginning of the curve the edge radius is tangent to
    x_f = float(x_f)  # the end of the curve the edge radius is tangent to
    R = float(R)  # The R_0 for the curve the edge radius is tangent to
    K = float(K)  # The conic constant, K, for the curve the edge radius is tangent to
    m = float(
        m
    )  # The slope of the line that is the edge boundary, this must not be verticle that is why this needs to be the line in the CS of the curve tangent to the edge radius
    b = float(
        b
    )  # The y-intercept of the line that is the edge boundary, this must not be verticle that is why this needs to be the line in the CS of the curve tangent to the edge radius
    r = float(r)  # The radius of the edge

    def original_curve(x):
        return -(x**2) / (R + np.sqrt(R**2 - (K + 1) * x**2))

    def derivative_curve(x):
        numerator = -2 * x * (R + np.sqrt(R**2 - (K + 1) * x**2))
        denominator = (R + np.sqrt(R**2 - (K + 1) * x**2)) ** 2
        return numerator / denominator

    def offset_curve(x):
        dy_dx = derivative_curve(x)
        nx = -dy_dx
        ny = 1
        norm = np.sqrt(nx**2 + ny**2)
        nx, ny = nx / norm, ny / norm
        return original_curve(x) - ny * r

    def calculate_offset_line_corr(x, m, b, r, direction):
        d = r * direction
        v_normal = (
            1 / np.sqrt(1 + (-1 / m) ** 2),
            (-1 / m) / np.sqrt(1 + (-1 / m) ** 2),
        )
        x_o1 = d * v_normal[0]
        y_o1 = b + d * v_normal[1]
        b_o = y_o1 - m * x_o1
        return m * x + b_o

    def find_intersection(x_guess):
        def equations(x):
            return offset_curve(x) - calculate_offset_line_corr(x, m, b, r, direction)

        (x_intersection,) = fsolve(equations, x_guess, xtol=1.49012e-08, maxfev=1000)
        # Ensure the solution is within the specified range before returning it
        if x_i <= x_intersection <= x_f:
            return x_intersection, offset_curve(x_intersection)
        else:
            return None, None  # Indicate no valid solution in range

    # Use the midpoint of the specified x range as an initial guess
    x_guess = (x_i + x_f) / 2.0
    h, k = find_intersection(x_guess)

    if h is not None and k is not None:
        return h, k
    else:
        raise ValueError("No valid intersection found in the specified x range.")


def calculate_offset_curve(x_vals, y_vals, offset_distance):
    # This creats an curve parallel to the input curve at an offset distance
    # The starting curve is defined by a list of x values and the corresponding list of y values.
    # Calculate the gradients (dy/dx)
    dy = np.gradient(y_vals, x_vals)
    dx = np.gradient(x_vals, x_vals)
    slopes = dy / dx

    # Calculate normal vectors (-dy, dx)
    normals = np.array([-dy, dx])
    norm_lengths = np.linalg.norm(normals, axis=0)
    unit_normals = normals / norm_lengths

    # Offset the curve
    offset_curve_x = x_vals + unit_normals[0] * offset_distance
    offset_curve_y = y_vals + unit_normals[1] * offset_distance

    return offset_curve_x, offset_curve_y


def generate_circle(center_x, center_y, radius, num_points=100):
    # Generates a list of x and y values for the perimeter of a circle
    # Generate angles
    angles = np.linspace(0, 2 * np.pi, num_points)

    # Calculate x and y values
    x_vals = center_x + radius * np.cos(angles)
    y_vals = center_y + radius * np.sin(angles)

    return x_vals, y_vals


def generate_partial_circle_counterclockwise(
    center_x, center_y, radius, start_x, end_x, num_points=100
):
    # Calculate the angle for the starting x value (top half of the circle)
    if np.abs(start_x - center_x) > radius:
        raise ValueError("The starting x value is outside the circle.")
    start_angle = np.arccos((start_x - center_x) / radius)

    # Calculate the angle for the ending x value (bottom half of the circle)
    if np.abs(end_x - center_x) > radius:
        raise ValueError("The ending x value is outside the circle.")
    end_angle = 2 * np.pi - np.arccos((end_x - center_x) / radius)

    if end_angle <= start_angle:
        raise ValueError(
            "The end x value should correspond to a point in the bottom half of the circle."
        )

    # Generate angles from start_angle to end_angle
    angles = np.linspace(start_angle, end_angle, num_points)

    # Calculate x and y values
    x_vals = center_x + radius * np.cos(angles)
    y_vals = center_y + radius * np.sin(angles)

    # Return the list of points
    # points = list(zip(x_vals, y_vals))
    return x_vals, y_vals


def generate_partial_circle_clockwise(
    center_x, center_y, radius, start_x, end_x, num_points=100
):
    # Calculate the angle for the starting x value (top half of the circle)
    if np.abs(start_x - center_x) > radius:
        raise ValueError("The starting x value is outside the circle.")
    start_angle = np.arccos((start_x - center_x) / radius)

    # Calculate the angle for the ending x value (bottom half of the circle)
    if np.abs(end_x - center_x) > radius:
        raise ValueError("The ending x value is outside the circle.")
    end_angle = -np.arccos((end_x - center_x) / radius)

    if start_angle <= end_angle:
        raise ValueError(
            "The end x value should correspond to a point lower than the start x value on the circle (for clockwise direction)."
        )

    # Generate angles from start_angle to end_angle in clockwise direction
    angles = np.linspace(start_angle, end_angle, num_points)

    # Calculate x and y values
    x_vals = center_x + radius * np.cos(angles)
    y_vals = center_y + radius * np.sin(angles)

    # Return the list of points
    # points = list(zip(x_vals, y_vals))
    return x_vals, y_vals


def generate_bottom_right_quadrant_of_circle(
    center_x, center_y, radius, start_x, end_x, num_points=100
):
    # Validate that the start_x and end_x are within the bottom right quadrant
    if start_x < center_x or start_x > center_x + radius:
        raise ValueError(
            "The starting x value should be within the bottom right quadrant of the circle."
        )
    if end_x < center_x or end_x > center_x + radius:
        raise ValueError(
            "The ending x value should be within the bottom right quadrant of the circle."
        )

    # Calculate the corresponding y values for start_x and end_x
    start_y = center_y - np.sqrt(radius**2 - (start_x - center_x) ** 2)
    end_y = center_y - np.sqrt(radius**2 - (end_x - center_x) ** 2)

    # Calculate the start and end angles using arctan2
    start_angle = np.arctan2(start_y - center_y, start_x - center_x)
    end_angle = np.arctan2(end_y - center_y, end_x - center_x)

    # Adjust the angles to ensure they are in the correct quadrant (270° to 360°)
    if start_angle < 0:
        start_angle += 2 * np.pi
    if end_angle < 0:
        end_angle += 2 * np.pi

    # Ensure the angles are between 270° and 360° (3π/2 to 2π radians)
    if not (3 * np.pi / 2 <= start_angle <= 2 * np.pi):
        raise ValueError(
            "The start x value should correspond to an angle between 270° and 360°."
        )
    if not (3 * np.pi / 2 <= end_angle <= 2 * np.pi):
        raise ValueError(
            "The end x value should correspond to an angle between 270° and 360°."
        )

    # Generate angles from start_angle to end_angle
    angles = np.linspace(start_angle, end_angle, num_points)

    # Calculate x and y values
    x_vals = center_x + radius * np.cos(angles)
    y_vals = center_y + radius * np.sin(angles)

    # Return the list of points
    return x_vals, y_vals


# Find tangent points on a circle of a line from a point outside the line
def tangent_points_to_circle(h, k, r, xp, yp):
    A = xp - h
    B = yp - k
    D = A**2 + B**2  # Calculating D as A^2 + B^2

    # Calculating x coordinates for the tangent points
    x12_part1 = r**2 * A / D
    x12_part2 = r * B / D * np.sqrt(D - r**2)
    x1 = x12_part1 + x12_part2 + h
    x2 = x12_part1 - x12_part2 + h

    # Calculating y coordinates for the tangent points
    y12_part1 = r**2 * B / D
    y12_part2 = r * A / D * np.sqrt(D - r**2)
    y1 = y12_part1 - y12_part2 + k
    y2 = y12_part1 + y12_part2 + k

    return (x1, y1), (x2, y2)


def point_of_intersection_curve_line(x_curve, y_curve, slope, y_intercept):
    """
    A method to find the point of intersection between a curve (defined by series of points)
    and a line (defined by its slope and y-intercept).  Interpolate the curve to get a
    continuous representation of it, then solve for the intersection point by finding where
    the line and the interpolated curve have the same y values for a given x. This involves
    a root-finding techniques for the equation representing the difference between the line
    and the curve.
    """
    # Define your curve through x and y points
    x_points = x_curve
    y_points = y_curve

    # Define the line by its slope (m) and y-intercept (b)
    m = slope  # Slope of the line
    b = y_intercept  # y-intercept of the line

    # Interpolate the curve
    curve_interp = interp1d(x_points, y_points, kind="cubic")

    # Define a function that calculates the difference between the line and the curve
    def difference(x):
        y_line = m * x + b
        y_curve = curve_interp(x)
        return y_line - y_curve

    # Use root_scalar to find where the difference is 0 (i.e., the intersection point)
    # Make sure the bracket spans the domain of your curve
    # x_min = x_points.min()
    # x_max = x_points.max()
    x_min = min(x_points)
    x_max = max(x_points)
    result = root_scalar(difference, bracket=[x_min, x_max])

    if result.converged:
        x_intersection = result.root
        y_intersection = m * x_intersection + b
        # print(f"Intersection point: ({x_intersection}, {y_intersection})")
        return (x_intersection, y_intersection)
    else:
        raise ValueError("No valid intersection found in the specified x range.")


def calculate_angle(C, P):
    """
    Calculate the angles of line CP relative to the horizontal line from C.

    Parameters:
    C (tuple): Center point (x, y).
    P (tuple): Starting point (x, y).

    Returns:
    Angle of CP in radians, relative to the positive x direction.
    """
    # Calculate differences in coordinates
    delta_x, delta_y = P_i[0] - C[0], P_i[1] - C[1]

    # Calculate angles using arctan2
    angle_CP = np.arctan2(delta_y, delta_x)

    return angle_CP


def cubic_interpolate(x_points, y_points, x):
    # Create the interpolating function with cubic interpolation
    interpolating_function = interp1d(
        x_points, y_points, kind="cubic", fill_value="extrapolate"
    )

    # Compute the interpolated value
    y = interpolating_function(x)
    return y


def expand_and_extrapolate(x_points, y_points, x_target, num_extra_points=100):
    """
    Expand the x and y lists to include values up to the x_target by extrapolating.

    Parameters:
    - x_points: list of original x values (must be sorted in ascending order)
    - y_points: list of corresponding y values
    - x_target: the target x value to extrapolate towards
    - num_extra_points: the number of extrapolated points to generate between the last x point and x_target

    Returns:
    - new_x_points: expanded list of x values including extrapolated values
    - new_y_points: corresponding y values including extrapolated values
    """
    # Create the interpolating function with cubic interpolation and extrapolation
    interpolating_function = interp1d(
        x_points, y_points, kind="cubic", fill_value="extrapolate"
    )

    # Generate new x points from the last original x to x_target
    if x_target > x_points[-1]:
        new_x_points = np.linspace(x_points[-1], x_target, num_extra_points + 1)[1:]
    else:
        new_x_points = np.linspace(x_target, x_points[0], num_extra_points + 1)[1:]

    # Compute the corresponding y values using extrapolation
    new_y_points = interpolating_function(new_x_points)

    # Combine the original and new points
    if x_target > x_points[-1]:
        expanded_x_points = np.concatenate((x_points, new_x_points))
        expanded_y_points = np.concatenate((y_points, new_y_points))
    else:
        expanded_x_points = np.concatenate((new_x_points[::-1], x_points))
        expanded_y_points = np.concatenate((new_y_points[::-1], y_points))

    return expanded_x_points, expanded_y_points


def ensure_strictly_increasing(x_points, y_points):
    """
    Ensures that x_points are strictly increasing by removing duplicates or out-of-order values.

    Args:
        x_points (list of float): List of x values.
        y_points (list of float): List of y values corresponding to x_points.

    Returns:
        tuple: Filtered lists of x_points and y_points with strictly increasing x values.
    """
    # Initialize lists for strictly increasing values
    x_filtered = [x_points[0]]
    y_filtered = [y_points[0]]

    # Filter out non-increasing x values
    for i in range(1, len(x_points)):
        if x_points[i] > x_filtered[-1]:  # Only add if strictly greater
            x_filtered.append(x_points[i])
            y_filtered.append(y_points[i])

    return x_filtered, y_filtered


def compute_tangent_line(x_val, x_points, y_points):
    """
    Computes the tangent line at a given x value on a curve defined by x_points and y_points.

    Args:
        x_val (float): The x value at which to compute the tangent line.
        x_points (list of float): List of x values defining the curve.
        y_points (list of float): List of y values defining the curve.

    Returns:
        tuple: Slope and y-intercept of the tangent line.
    """
    x_points, y_points = ensure_strictly_increasing(x_points, y_points)
    x_points = np.array(x_points)
    y_points = np.array(y_points)

    # Step 1: Interpolate the curve using Cubic Spline
    cs = CubicSpline(x_points, y_points)

    # Step 2: Differentiate the curve to find the slope (dy/dx)
    cs_derivative = cs.derivative()

    # Step 3: Compute the slope of the tangent line at x_val
    slope_tangent = cs_derivative(x_val)

    # Compute the y value at x_val on the curve
    y_val = cs(x_val)

    # Step 4: Compute the tangent line
    # y = mx + b => b = y - mx
    b_tangent = y_val - slope_tangent * x_val

    return slope_tangent, b_tangent


def compute_tangent_line_b(x_val, x_points, y_points):
    """
    Computes the tangent line at a given x value on a curve defined by x_points and y_points.

    Args:
        x_val (float): The x value at which to compute the tangent line.
        x_points (list of float): List of x values defining the curve.
        y_points (list of float): List of y values defining the curve.

    Returns:
        tuple: Slope and y-intercept of the tangent line.
    """
    x_points, y_points = ensure_strictly_increasing(x_points, y_points)
    x_points = np.array(x_points)
    y_points = np.array(y_points)

    # Step 1: Find the closest 15 points before and 15 points after x_val
    indices = np.argsort(np.abs(x_points - x_val))
    selected_indices = indices[
        :30
    ]  # Select 30 closest points (15 before and 15 after x_val)

    selected_x = x_points[selected_indices]
    selected_y = y_points[selected_indices]

    # Step 2: Interpolate the curve using Barycentric Interpolator
    interpolator = BarycentricInterpolator(selected_x, selected_y)

    # Step 3: Estimate the slope (dy/dx) using central difference
    delta = 1e-6  # Small change in x for numerical derivative
    slope_tangent = (interpolator(x_val + delta) - interpolator(x_val - delta)) / (
        2 * delta
    )

    # Step 4: Compute the y value at x_val using the interpolator
    y_val = interpolator(x_val)

    # Step 5: Compute the y-intercept of the tangent line
    # y = mx + b  =>  b = y - mx
    b_tangent = y_val - slope_tangent * x_val

    return slope_tangent, b_tangent


def compute_normal_line(x_val, x_points, y_points):
    """
    Computes the normal line at a given x value on a curve defined by x_points and y_points.

    Args:
        x_val (float): The x value at which to compute the normal line.
        x_points (list of float): List of x values defining the curve.
        y_points (list of float): List of y values defining the curve.

    Returns:
        tuple: Slope and y-intercept of the normal line.
    """
    x_points, y_points = ensure_strictly_increasing(x_points, y_points)
    slope_tangent, _ = compute_tangent_line(x_val, x_points, y_points)

    # Step 1: Compute the slope of the normal line (negative reciprocal of tangent slope)
    if slope_tangent != 0:
        slope_normal = -1 / slope_tangent
    else:
        slope_normal = float(
            "inf"
        )  # Handle the case where the tangent line is horizontal

    # Step 2: Compute the y value at x_val on the curve
    x_points = np.array(x_points)
    y_points = np.array(y_points)
    cs = CubicSpline(x_points, y_points)
    y_val = cs(x_val)

    # Step 3: Compute the normal line
    # y = mx + b => b = y - mx
    if slope_normal != float("inf"):
        b_normal = y_val - slope_normal * x_val
    else:
        b_normal = None  # No y-intercept for a vertical line

    # Generate points for the normal line for plotting
    if slope_normal != float("inf"):
        x_normal = np.linspace(x_val - 1, x_val + 1, 100)
        y_normal = slope_normal * x_normal + b_normal
    else:
        x_normal = np.array([x_val, x_val])
        y_normal = np.linspace(y_val - 1, y_val + 1, 100)

    return slope_normal, b_normal


def concatenate_points(*points_lists):
    """
    Concatenates multiple lists of x and y values while removing duplicate points.

    Args:
        *points_lists: Tuples containing lists of x and y values. Each tuple is (x_list, y_list).

    Returns:
        tuple: Two lists containing the concatenated x and y values without duplicates.
    """
    concatenated_x = []
    concatenated_y = []
    seen_points = set()

    for x_list, y_list in points_lists:
        for x, y in zip(x_list, y_list):
            if (x, y) not in seen_points:
                concatenated_x.append(x)
                concatenated_y.append(y)
                seen_points.add((x, y))

    return concatenated_x, concatenated_y


def truncate_points(x0, y0, x1, y1):
    """
    Truncates the first set of points (x0, y0) such that the last point
    in the truncated list corresponds to the first point in the second set of points (x1, y1).

    Args:
        x0: List of x values for the first set of points.
        y0: List of y values for the first set of points.
        x1: List of x values for the second set of points.
        y1: List of y values for the second set of points.

    Returns:
        tuple: Two lists containing the truncated x and y values from the first set.
    """
    import numpy as np

    first_point_x1 = x1[0]
    first_point_y1 = y1[0]

    # Calculate distances from the first point of the second set to all points in the first set
    distances = [
        np.sqrt((x - first_point_x1) ** 2 + (y - first_point_y1) ** 2)
        for x, y in zip(x0, y0)
    ]

    # Find the index of the closest point
    closest_index = np.argmin(distances)

    # Check if the closest point in x0, y0 is the same as the first point in x1, y1
    if x0[closest_index] == first_point_x1 and y0[closest_index] == first_point_y1:
        truncated_x = x0[: closest_index + 1]
        truncated_y = y0[: closest_index + 1]
    else:
        # Include the exact first point of the second set if it's not already present
        truncated_x = x0[: closest_index + 1] + [first_point_x1]
        truncated_y = y0[: closest_index + 1] + [first_point_y1]

    return truncated_x, truncated_y


def truncate_and_interpolate(x_list, y_list, x_truncate):
    # print(f"Input x_list: {x_list}")
    # print(f"Input y_list: {y_list}")
    # print(f"x_truncate: {x_truncate}")

    # Ensure x_list is sorted; if not, sort both x_list and y_list accordingly
    if not all(x_list[i] <= x_list[i + 1] for i in range(len(x_list) - 1)):
        # print("Sorting x_list and y_list as they are not sorted.")
        sorted_indices = np.argsort(x_list)
        x_list = np.array(x_list)[sorted_indices].tolist()
        y_list = np.array(y_list)[sorted_indices].tolist()

    # Find the indices between which the x_truncate lies
    for i in range(len(x_list) - 1):
        # print(f"Checking range: x_list[{i}] = {x_list[i]}, x_list[{i + 1}] = {x_list[i + 1]}")
        if x_list[i] <= x_truncate <= x_list[i + 1]:
            # print(f"x_truncate {x_truncate} is between x_list[{i}] = {x_list[i]} and x_list[{i + 1}] = {x_list[i + 1]}")

            # Perform linear interpolation to find the corresponding y value
            y_truncate = y_list[i] + (y_list[i + 1] - y_list[i]) * (
                x_truncate - x_list[i]
            ) / (x_list[i + 1] - x_list[i])
            # print(f"Interpolated y_truncate: {y_truncate}")

            # Truncate the lists up to the desired point
            x_truncated = x_list[
                : i + 1
            ]  # + [x_truncate]  # Explicitly create a new list up to the truncation point
            y_truncated = y_list[: i + 1]  # + [y_truncate]  # Same for y_list

            # print(f"Truncated x_list: {x_truncated}")
            # print(f"Truncated y_list: {y_truncated}")

            return x_truncated, y_truncated

    # If x_truncate is outside the range of x_list, return original lists
    print("x_truncate is outside the range of x_list.")
    return x_list.copy(), y_list.copy()


import numpy as np


def truncate_and_interpolate_from_x(x_list, y_list, x_truncate):
    # Ensure the lists are sorted by x_list
    if not all(x_list[i] <= x_list[i + 1] for i in range(len(x_list) - 1)):
        sorted_indices = np.argsort(x_list)
        x_list = np.array(x_list)[sorted_indices].tolist()
        y_list = np.array(y_list)[sorted_indices].tolist()

    # Step 1: Use CubicSpline to interpolate the y value for x_truncate
    spline = CubicSpline(x_list, y_list)
    y_truncate = spline(x_truncate).item()

    # Step 2: Initialize the new lists with the interpolated values at x_truncate
    x_new = [x_truncate]
    y_new = [y_truncate]

    # Step 3 and 4: Add remaining points from the original lists after x_truncate
    for i in range(len(x_list)):
        if x_list[i] > x_truncate:  # Add points strictly after x_truncate
            x_new.append(x_list[i])
            y_new.append(y_list[i])

    return x_new, y_new


def preprocess_points(x_points, y_points):
    """
    This process point so that they will work with cubic interpolation.
        Combines x and y points.
        Sorts the combined points by x values.
        Removes duplicates and ensures x values are strictly increasing.
        Separates the sorted and unique x and y values.
    """
    # Combine x and y points
    points = list(zip(x_points, y_points))

    # Sort points by x values
    points.sort()

    # Remove duplicates and ensure x values are strictly increasing
    unique_points = []
    for i in range(len(points)):
        if i == 0 or points[i][0] > points[i - 1][0]:
            unique_points.append(points[i])

    # Separate x and y values
    x_points_sorted = [p[0] for p in unique_points]
    y_points_sorted = [p[1] for p in unique_points]

    return x_points_sorted, y_points_sorted


def find_intersection(slope, intercept, x_points, y_points):
    # Intersection of a line and a curve
    # Define the line function
    def line(x):
        return slope * x + intercept

    # Interpolate the curve
    curve = interp1d(x_points, y_points, kind="cubic", fill_value="extrapolate")

    # Define the difference function
    def difference(x):
        return curve(x) - line(x)

    # Use fsolve to find the x values where the difference is zero
    # Make an initial guess based on the x_points
    initial_guesses = np.linspace(min(x_points), max(x_points), 100)
    intersections = fsolve(difference, initial_guesses)

    # Filter out the valid intersections within the range of x_points
    valid_intersections = []
    for x in intersections:
        if min(x_points) <= x <= max(x_points):
            valid_intersections.append(x)

    # Remove duplicates
    valid_intersections = np.unique(valid_intersections)
    return sum(valid_intersections) / len(valid_intersections)


def truncate_at_x(x_values, y_values, x_truncate):
    """
    Truncate the lists of x-values and y-values at the given x value, interpolating if necessary.

    Parameters:
    x_values (list of float): List of x-values.
    y_values (list of float): List of y-values.
    x_truncate (float): The x value at which to truncate the lists.

    Returns:
    tuple: Truncated lists of x-values and y-values.
    """
    # Ensure the lists are sorted by x_values
    sorted_pairs = sorted(zip(x_values, y_values))
    x_values_sorted, y_values_sorted = zip(*sorted_pairs)

    # Find the index where x_values exceeds or equals x_truncate
    index = 0
    for i, x in enumerate(x_values_sorted):
        if x >= x_truncate:
            index = i
            break
    else:
        # If x_truncate is greater than all x_values, return the full list
        return list(x_values_sorted), list(y_values_sorted)

    # Truncate the lists at the found index
    truncated_x_values = list(x_values_sorted[: index + 1])
    truncated_y_values = list(y_values_sorted[: index + 1])

    # Check if the last x value is exactly x_truncate
    if truncated_x_values[-1] != x_truncate:
        # Interpolate the y value at x_truncate
        x1, y1 = x_values_sorted[index - 1], y_values_sorted[index - 1]
        x2, y2 = x_values_sorted[index], y_values_sorted[index]
        interpolated_y = y1 + (y2 - y1) * (x_truncate - x1) / (x2 - x1)
        truncated_x_values[-1] = x_truncate
        truncated_y_values[-1] = interpolated_y

    return truncated_x_values, truncated_y_values


def blend_curves(x1, y1, x2, y2, blend_radius):
    """
    This is to blend two curves with a blend radius.
    Both curves are defined with a list of x and y values abd are arguments: x1, y1, x2, y2.
    Curve 1 must end where curve 2 starts.
    """

    # Ensure the input lists are numpy arrays
    x1 = np.array(x1)
    y1 = np.array(y1)
    x2 = np.array(x2)
    y2 = np.array(y2)

    # Determine the transition points
    end_point1 = (x1[-1], y1[-1])
    start_point2 = (x2[0], y2[0])

    # Check if points are close enough within tolerance
    distance = np.linalg.norm(np.array(end_point1) - np.array(start_point2))
    if distance > 0.01:
        raise ValueError(
            "The end point of the first curve and the start point of the second curve are too far apart."
        )

    # Calculate the number of points in the blend region
    delta_x = x2[0] - x1[-1]
    if np.abs(delta_x) < 1e-6:  # Handle the case where delta_x is zero or close to zero
        blend_x = np.array([x1[-1]])
        blend_y = np.array([end_point1[1]])
    else:
        num_points = max(int(blend_radius / delta_x) + 2, 3)
        blend_x = np.linspace(x1[-1], x2[0], num=num_points)

        # Define a Hermite spline for smooth transition
        # We use derivatives (slopes) at the endpoints to ensure smoothness
        if len(x1) > 1:
            slope1 = (y1[-1] - y1[-2]) / (x1[-1] - x1[-2])
        else:
            slope1 = 0  # Default slope if there's only one point

        if len(x2) > 1:
            slope2 = (y2[1] - y2[0]) / (x2[1] - x2[0])
        else:
            slope2 = 0  # Default slope if there's only one point

        hermite_spline = CubicHermiteSpline(
            [x1[-1], x2[0]], [y1[-1], y2[0]], [slope1, slope2]
        )
        blend_y = hermite_spline(blend_x)

    # Concatenate the curves
    x_blended = np.concatenate((x1, blend_x[1:], x2[1:]))
    y_blended = np.concatenate((y1, blend_y[1:], y2[1:]))

    return x_blended, y_blended


def blend_curves2(x1, y1, x2, y2, blend_radius, d):
    """
    Blend two curves with a blend radius and a specified distance d from the ends of each curve.

    Arguments:
    x1, y1 -- Lists or arrays representing the x and y coordinates of curve 1.
    x2, y2 -- Lists or arrays representing the x and y coordinates of curve 2.
    blend_radius -- The radius over which the blending occurs.
    d -- The distance from the end of curve 1 and the start of curve 2 where blending should start/end.

    Curve 1 must end where curve 2 starts.
    """

    # Ensure the input lists are numpy arrays
    x1 = np.array(x1)
    y1 = np.array(y1)
    x2 = np.array(x2)
    y2 = np.array(y2)

    # Determine the transition points
    end_point1 = (x1[-1], y1[-1])
    start_point2 = (x2[0], y2[0])

    # Check if points are close enough within tolerance
    distance = np.linalg.norm(np.array(end_point1) - np.array(start_point2))
    if distance > 0.01:
        raise ValueError(
            "The end point of the first curve and the start point of the second curve are too far apart."
        )

    # Determine points to start and end the blending process
    x1_blend_start_index = np.argmax(x1 >= x1[-1] - d)
    x2_blend_end_index = np.argmax(x2 >= x2[0] + d)

    x1_blend_start = x1[x1_blend_start_index]
    y1_blend_start = y1[x1_blend_start_index]
    x2_blend_end = x2[x2_blend_end_index]
    y2_blend_end = y2[x2_blend_end_index]

    # Calculate the number of points in the blend region
    delta_x = x2_blend_end - x1_blend_start
    if np.abs(delta_x) < 1e-6:  # Handle the case where delta_x is zero or close to zero
        blend_x = np.array([x1_blend_start])
        blend_y = np.array([y1_blend_start])
    else:
        num_points = max(int(blend_radius / delta_x) + 2, 3)
        blend_x = np.linspace(x1_blend_start, x2_blend_end, num=num_points)

        # Define a Hermite spline for smooth transition
        # We use derivatives (slopes) at the endpoints to ensure smoothness
        if len(x1) > 1:
            slope1 = (y1[-1] - y1[-2]) / (x1[-1] - x1[-2])
        else:
            slope1 = 0  # Default slope if there's only one point

        if len(x2) > 1:
            slope2 = (y2[1] - y2[0]) / (x2[1] - x2[0])
        else:
            slope2 = 0  # Default slope if there's only one point

        hermite_spline = CubicHermiteSpline(
            [x1_blend_start, x2_blend_end],
            [y1_blend_start, y2_blend_end],
            [slope1, slope2],
        )
        blend_y = hermite_spline(blend_x)

    # Concatenate the curves
    x_blended = np.concatenate(
        (x1[:x1_blend_start_index], blend_x, x2[x2_blend_end_index:])
    )
    y_blended = np.concatenate(
        (y1[:x1_blend_start_index], blend_y, y2[x2_blend_end_index:])
    )

    return x_blended, y_blended


def generate_evenly_spaced_points(x_values, y_values, spacing):
    """
    Generate new x and y lists with evenly spaced x values.
    The points are evenly spaced along the curve.  Spacing is not constrained to a single axis.

    Parameters:
    x_values (list of float): List of x-values.
    y_values (list of float): List of y-values.
    spacing (float): Desired spacing between the new x values.

    Returns:
    tuple: New lists of x-values and y-values with evenly spaced x values.
    """
    # Ensure the input lists are numpy arrays
    x_values = np.array(x_values)
    y_values = np.array(y_values)

    # Calculate cumulative distances along the curve
    distances = np.sqrt(np.diff(x_values) ** 2 + np.diff(y_values) ** 2)
    cumulative_distances = np.concatenate([[0], np.cumsum(distances)])

    # Calculate the total length of the curve
    total_length = cumulative_distances[-1]

    # Calculate the number of points needed
    num_points = round(total_length / spacing) + 1

    # Recalculate the adjusted spacing
    adjusted_spacing = total_length / (num_points - 1)

    # Generate the new evenly spaced distances
    new_distances = np.linspace(0, total_length, num=num_points)

    # Interpolate the new x and y values
    new_x_values = np.interp(new_distances, cumulative_distances, x_values)
    new_y_values = np.interp(new_distances, cumulative_distances, y_values)

    return list(new_x_values), list(new_y_values)


def generate_evenly_spaced_points_2(x_values, y_values, no_of_points):
    """
    Generate new x and y lists with evenly spaced x values.
    The points are evenly spaced along the curve.  Spacing is not constrained to a single axis.

    Parameters:
    x_values (list of float): List of x-values.
    y_values (list of float): List of y-values.
    spacing (float): Desired spacing between the new x values.

    Returns:
    tuple: New lists of x-values and y-values with evenly spaced x values.
    """
    num_points = int(no_of_points)

    # Ensure the input lists are numpy arrays
    x_values = np.array(x_values)
    y_values = np.array(y_values)

    # Calculate cumulative distances along the curve
    distances = np.sqrt(np.diff(x_values) ** 2 + np.diff(y_values) ** 2)
    cumulative_distances = np.concatenate([[0], np.cumsum(distances)])

    # Calculate the total length of the curve
    total_length = cumulative_distances[-1]

    # Calculate the number of points needed
    # num_points = round(total_length / spacing) + 1

    # Recalculate the adjusted spacing
    adjusted_spacing = total_length / (num_points - 1)

    # Generate the new evenly spaced distances
    new_distances = np.linspace(0, total_length, num=num_points)

    # Interpolate the new x and y values
    new_x_values = np.interp(new_distances, cumulative_distances, x_values)
    new_y_values = np.interp(new_distances, cumulative_distances, y_values)

    return list(new_x_values), list(new_y_values)


def write_b_side_file(Header, Surface, points_x, points_y, filename):
    """
    Writes the contents of the Header and Surface dictionaries and point lists to a text file for the "b" side.

    Parameters:
    Header (dict): The dictionary containing header information.
    Surface (dict): The dictionary containing surface definition information.
    points_x (list): List of x-values of points.
    points_y (list): List of y-values of points.
    filename (str): The name of the file to write, excluding the ".V5B" extension.
    """
    full_filename = filename + ".V5B"

    with open(full_filename, "w") as file:
        # Write the Header section
        for key, value in Header.items():
            value_str = str(value["value"])
            description_str = value["description"]
            line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the surface definition header
        surface_number = Surface.get("Number", 1)
        file.write(f"\\-- SURFACE DEFINITION #{surface_number} --\n")

        # Write the Surface section
        for key, value in Surface.items():
            if key == "Number":
                continue  # Skip the Number entry as it is used in the header

            value_str = str(value["value"])
            description_str = value["description"]

            # Prepend a "\" if the condition is met
            if Header["non_rotationally_symmetrical"]["value"] == 0 and key in [
                "num_radial_defs",
                "rotation_angle",
            ]:
                line = f"\\{value_str:<19}\\ {description_str}"
            else:
                line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the radial definition header
        file.write("\\ --- radial definition ---\n")

        # Write the number of points
        num_points = len(points_x)
        file.write(f"{num_points:<20}\\ # pts in radial\n")

        # Write the points in reverse order
        for x, y in zip(reversed(points_x), reversed(points_y)):
            line = f"{x:.4f} ; {y}"
            file.write(line + "\n")


def write_b_side_file2(Header, Surface, points_x, points_y, filename):
    """
    Writes the contents of the Header and Surface dictionaries and point lists to a text file for the "b" side.

    Parameters:
    Header (dict): The dictionary containing header information.
    Surface (dict): The dictionary containing surface definition information.
    points_x (list of lists): List of lists containing x-values of points.
    points_y (list of lists): List of lists containing y-values of points.
    filename (str): The name of the file to write, excluding the ".V5B" extension.
    """
    full_filename = filename + ".V5B"

    with open(full_filename, "w") as file:
        # Write the Header section
        for key, value in Header.items():
            value_str = str(value["value"])
            description_str = value["description"]
            line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the surface definition header
        surface_number = Surface.get("Number", 1)
        file.write(f"\\-- SURFACE DEFINITION #{surface_number} --\n")

        # Write the Surface section
        for key, value in Surface.items():
            if key == "Number":
                continue  # Skip the Number entry as it is used in the header

            value_str = str(value["value"])
            description_str = value["description"]

            # Prepend a "\" if the condition is met
            if Header["non_rotationally_symmetrical"]["value"] == 0 and key in [
                "num_radial_defs",
                "rotation_angle",
            ]:
                line = f"\\{value_str:<19}\\ {description_str}"
            else:
                line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the radial definition header
        file.write("\\ --- radial definition ---\n")

        # Iterate over each sublist in points_x and points_y
        for idx, (sublist_x, sublist_y) in enumerate(zip(points_x, points_y)):
            # Ensure the sublists have the same number of points
            if len(sublist_x) != len(sublist_y):
                raise ValueError(
                    f"Mismatch in number of points between x and y sublists at index {idx}."
                )

            # Write the number of points in the current sublist
            num_points = len(sublist_x)
            file.write(f"{num_points:<20}\\ # pts in radial\n")

            # Write the points in reverse order for the current sublist
            for x, y in zip(reversed(sublist_x), reversed(sublist_y)):
                # Convert y to standard decimal notation if needed
                y_standard = (
                    f"{y:.10f}".rstrip("0").rstrip(".")
                    if "e" in f"{y}" or "E" in f"{y}"
                    else f"{y:.10f}".rstrip("0").rstrip(".")
                )
                line = f"{x:.4f} ; {y_standard}"
                file.write(line + "\n")


def write_f_side_file(Header, Surface, points_x, points_y, filename):
    """
    Writes the contents of the Header and Surface dictionaries and point lists to a text file for the "f" side.

    Parameters:
    Header (dict): The dictionary containing header information.
    Surface (dict): The dictionary containing surface definition information.
    points_x (list): List of x-values of points.
    points_y (list): List of y-values of points.
    filename (str): The name of the file to write, excluding the ".V5F" extension.
    """
    full_filename = filename + ".V5F"

    # Adjust points_y for the "f" side by subtracting points_y[-1] and ensuring positive values
    last_y_value = points_y[-1]
    adjusted_points_y = [y - last_y_value for y in points_y]

    with open(full_filename, "w") as file:
        # Write the Header section
        for key, value in Header.items():
            value_str = str(value["value"])
            description_str = value["description"]
            line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the surface definition header
        surface_number = Surface.get("Number", 1)
        file.write(f"\\-- SURFACE DEFINITION #{surface_number} --\n")

        # Write the Surface section
        for key, value in Surface.items():
            if key == "Number":
                continue  # Skip the Number entry as it is used in the header

            value_str = str(value["value"])
            description_str = value["description"]

            # Prepend a "\" if the condition is met
            if Header["non_rotationally_symmetrical"]["value"] == 0 and key in [
                "angular_filtering",
                "num_radial_defs",
                "rotation_angle",
            ]:
                line = f"\\{value_str:<19}\\ {description_str}"
            else:
                line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the radial definition header
        file.write("\\ --- radial definition ---\n")

        # Write the number of points
        num_points = len(points_x)
        file.write(f"{num_points:<20}\\ # pts in radial\n")

        # Write the points in reverse order
        for x, y in zip(reversed(points_x), reversed(adjusted_points_y)):
            line = f"{x:.4f} ; {y + last_y_value}"  # Add last_y_value back to get correct positive y-values
            file.write(line + "\n")


def write_f_side_file2(Header, Surface, points_x, points_y, filename):
    """
    Writes the contents of the Header and Surface dictionaries and point lists to a text file for the "f" side.

    Parameters:
    Header (dict): The dictionary containing header information.
    Surface (dict): The dictionary containing surface definition information.
    points_x (list of lists): List of lists containing x-values of points.
    points_y (list of lists): List of lists containing y-values of points.
    filename (str): The name of the file to write, excluding the ".V5F" extension.
    """
    full_filename = filename + ".V5F"

    with open(full_filename, "w") as file:
        # Write the Header section
        for key, value in Header.items():
            value_str = str(value["value"])
            description_str = value["description"]
            line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the surface definition header
        surface_number = Surface.get("Number", 1)
        file.write(f"\\-- SURFACE DEFINITION #{surface_number} --\n")

        # Write the Surface section
        for key, value in Surface.items():
            if key == "Number":
                continue  # Skip the Number entry as it is used in the header

            value_str = str(value["value"])
            description_str = value["description"]

            # Prepend a "\" if the condition is met
            if Header["non_rotationally_symmetrical"]["value"] == 0 and key in [
                "angular_filtering",
                "num_radial_defs",
                "rotation_angle",
            ]:
                line = f"\\{value_str:<19}\\ {description_str}"
            else:
                line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the radial definition header
        file.write("\\ --- radial definition ---\n")

        # Iterate over each sublist in points_x and points_y
        for idx, (sublist_x, sublist_y) in enumerate(zip(points_x, points_y)):
            # Ensure the sublists have the same number of points
            if len(sublist_x) != len(sublist_y):
                raise ValueError(
                    f"Mismatch in number of points between x and y sublists at index {idx}."
                )

            # Adjust points_y for the "f" side by subtracting the last y-value of each sublist
            last_y_value = sublist_y[-1]
            adjusted_points_y = [y - last_y_value for y in sublist_y]

            # Write the number of points in the current sublist
            num_points = len(sublist_x)
            file.write(f"{num_points:<20}\\ # pts in radial\n")

            # Write the points in reverse order for the current sublist
            for x, y in zip(reversed(sublist_x), reversed(adjusted_points_y)):
                # Convert y to standard decimal notation if needed
                y_standard = (
                    f"{y + last_y_value:.10f}".rstrip("0").rstrip(".")
                    if "e" in f"{y}" or "E" in f"{y}"
                    else f"{y + last_y_value:.10f}".rstrip("0").rstrip(".")
                )

                line = f"{x:.4f} ; {y_standard}"
                file.write(line + "\n")


def write_f_side_file3(Header, Surface, points_x, points_y, filename):
    """
    Writes the contents of the Header and Surface dictionaries and point lists to a text file for the "f" side.

    Parameters:
    Header (dict): The dictionary containing header information.
    Surface (dict): The dictionary containing surface definition information.
    points_x (list of lists): List of lists containing x-values of points.
    points_y (list of lists): List of lists containing y-values of points.
    filename (str): The name of the file to write, excluding the ".V5F" extension.
    """
    full_filename = filename + ".V5F"

    with open(full_filename, "w") as file:
        # Write the Header section
        for key, value in Header.items():
            if key == "diag_marks":
                continue  # Skip diagnostic marks here, handle separately below

            value_str = str(value["value"])
            description_str = value["description"]
            line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Check if there are diagnostic marks
        num_diag_marks = Header.get("num_diag_marks", {}).get("value", 0)
        if num_diag_marks > 0:
            for mark in Header["diag_marks"]:
                # Writing each attribute of the diagnostic mark
                file.write(f"{mark['angle']:<20}\\ angle direction    {mark['note']}\n")
                file.write(
                    f"{mark['distance_from_edge']:<20}\\ distance from edge {mark['note']}\n"
                )
                file.write(
                    f"{mark['length']:<20}\\ length             {mark['note']}\n"
                )
                file.write(f"{mark['width']:<20}\\ width              {mark['note']}\n")

        # Write the surface definition header
        surface_number = Surface.get("Number", 1)
        file.write(f"\\-- SURFACE DEFINITION #{surface_number} --\n")

        # Write the Surface section
        for key, value in Surface.items():
            if key == "Number":
                continue  # Skip the Number entry as it is used in the header

            value_str = str(value["value"])
            description_str = value["description"]

            # Prepend a "\" if the condition is met
            if Header["non_rotationally_symmetrical"]["value"] == 0 and key in [
                "angular_filtering",
                "num_radial_defs",
                "rotation_angle",
            ]:
                line = f"\\{value_str:<19}\\ {description_str}"
            else:
                line = f"{value_str:<20}\\ {description_str}"
            file.write(line + "\n")

        # Write the radial definition header
        file.write("\\ --- radial definition ---\n")

        # Iterate over each sublist in points_x and points_y
        for idx, (sublist_x, sublist_y) in enumerate(zip(points_x, points_y)):
            # Ensure the sublists have the same number of points
            if len(sublist_x) != len(sublist_y):
                raise ValueError(
                    f"Mismatch in number of points between x and y sublists at index {idx}."
                )

            # Adjust points_y for the "f" side by subtracting the last y-value of each sublist
            last_y_value = sublist_y[-1]
            adjusted_points_y = [y - last_y_value for y in sublist_y]

            # Write the number of points in the current sublist
            num_points = len(sublist_x)
            file.write(f"{num_points:<20}\\ # pts in radial\n")

            # Write the points in reverse order for the current sublist
            for x, y in zip(reversed(sublist_x), reversed(adjusted_points_y)):
                # Convert y to standard decimal notation if needed
                y_standard = (
                    f"{y + last_y_value:.10f}".rstrip("0").rstrip(".")
                    if "e" in f"{y}" or "E" in f"{y}"
                    else f"{y + last_y_value:.10f}".rstrip("0").rstrip(".")
                )

                line = f"{x:.4f} ; {y_standard}"
                file.write(line + "\n")


def find_largest_number(numbers):
    # find the largest number in a list
    if not numbers:
        return None
    largest = numbers[0]
    for number in numbers:
        if number > largest:
            largest = number
    return largest


def segment_curve(x_values, y_values, start_x):
    """
    Segment a 2D curve defined by lists of x and y values starting from a specified x value.

    This function takes:
    - `x_values`: A list of x-coordinates which may not be strictly increasing.
    - `y_values`: Corresponding y-coordinates to `x_values`.
    - `start_x`: The x value from where to start the new curve segment.

    The function does the following:
    - Scans `x_values` to find the first occurrence of `start_x` or the first x value
      greater than `start_x`.
    - If `start_x` isn't found exactly, it interpolates the corresponding y value.
    - Returns new lists of x and y values starting from `start_x` or the interpolated point,
      including all subsequent values from the original lists.

    Parameters:
    x_values (list): List of x-coordinates.
    y_values (list): List of y-coordinates corresponding to x_values.
    start_x (float): The starting x value for the new segment.

    Returns:
    tuple: Two lists (new_x, new_y) representing the segmented curve.
    """

    # Convert lists to numpy arrays for easier manipulation
    x = np.array(x_values)
    y = np.array(y_values)

    # Find the index where we start our new curve
    start_index = np.searchsorted(x, start_x, side="left")

    if start_index == len(x):  # start_x is beyond the last x value
        return [], []

    # Check if we've found an exact match or need to interpolate
    if x[start_index] == start_x:
        new_x = x[start_index:]
        new_y = y[start_index:]
    else:
        # Interpolate y for the starting x
        if start_index == 0:  # If start_x is less than the first x, use the first y
            interpolated_y = y[0]
        else:
            slope = (y[start_index] - y[start_index - 1]) / (
                x[start_index] - x[start_index - 1]
            )
            interpolated_y = y[start_index - 1] + slope * (start_x - x[start_index - 1])

        # Construct new lists starting from interpolated point
        new_x = np.concatenate([[start_x], x[start_index:]])
        new_y = np.concatenate([[interpolated_y], y[start_index:]])

    return list(new_x), list(new_y)
