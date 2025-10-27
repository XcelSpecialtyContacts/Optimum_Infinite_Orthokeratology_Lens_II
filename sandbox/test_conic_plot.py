# sandbox/test_conic_plot.py
import pathlib, sys
# Add <repo>/src to sys.path so 'oiol2' is importable when running from repo root
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import matplotlib.pyplot as plt
from oiol2.geometry_core import slope_and_angle_of_line_tangent_to_curve
from oiol2.geometry_core import y_intercept

# Parameters
R0 = 1.0
K = 0.8
x_start = 0.0
x_end = 2.0

# Create x values
x = np.linspace(x_start, x_end, 500)

# Compute y values, ensuring the sqrt argument stays valid
sqrt_term = R0**2 - x**2 * (K + 1)
valid_mask = sqrt_term >= 0
x_valid = x[valid_mask]
y_valid = x_valid**2 / (R0 + np.sqrt(sqrt_term[valid_mask]))

# Plot the conic
plt.figure(figsize=(7, 5))
plt.plot(x_valid, y_valid, label=r"$y = \frac{x^2}{R_0 + \sqrt{R_0^2 - x^2(K+1)}}$", color="blue")

# === Compute and plot the tangent line at x = 0.5 ===
x_tangent = 0.5
#m, angle_rad, angle_deg = slope_and_angle_of_line_tangent_to_curve(x_tangent, R0, K)
m, _, _ = slope_and_angle_of_line_tangent_to_curve(x_tangent, R0, K)

# Calculate the y-value at x=0.5 on the conic
y_tangent = x_tangent**2 / (R0 + np.sqrt(R0**2 - x_tangent**2 * (K + 1)))

# Calculate the y-intercept (b)
b = y_intercept(x_tangent, y_tangent, m)

# Define tangent line (small range around x_tangent)
x_line = np.linspace(x_tangent - 0.2, x_tangent + 0.2, 50)
# y_line = m * (x_line - x_tangent) + y_tangent
y_line = m * x_line + b

# Compute slope of line norml to tangent line
m_n = -1/m

# Calculate the y-intercept (b_n) for line normal to tangent line that intercts tangent line at (x_tangent, y_tangent)
b_n = y_intercept(x_tangent, y_tangent, m_n)

# Define normal line (small range around x_tangent)
y_line_n = m_n * x_line + b_n

# Plot the normal line
plt.plot(x_line, y_line_n, "--r", label=f"Normal at x={x_tangent} (slope={float(m_n):.3f})")

# Highlight the point of tangency
plt.scatter([x_tangent], [y_tangent], color="red", zorder=5)

# Add labels, legend, etc.
plt.title("Conic Surface and Normal Line")
plt.xlabel("x")
plt.ylabel("y")
plt.legend()
plt.grid(True)
plt.axis("equal")

# Display results
print(f"x = {x_tangent}")
print(f"Slope Tangent = {float(m):.6f}")
#print(f"Angle (radians) = {float(angle_rad):.6f}")
#print(f"Angle (degrees) = {float(angle_deg):.3f}")
print(f"Slope Normal = {float(m_n):.6f}")

plt.show()
