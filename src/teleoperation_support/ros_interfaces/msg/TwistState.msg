# TwistState — per-side DexTwist diagnostics.
#
# Read-only observation. It never drives O10 control decisions. When a field is
# unavailable, the paired availability flag is false and the value is NaN; zero
# is never used as a substitute for "unknown".

std_msgs/Header header
string side
bool valid
bool active

# Tripod gate: aperture and extension are normalized by the frozen mean tripod
# chain length. Counts are the current consecutive on/off frame counters.
float64 gate_aperture
float64 gate_extension
uint32 gate_on_count
uint32 gate_off_count

# Human intent and robot progress. theta_increment is the per-episode target
# (theta_task - theta_base); the robot starts at zero on every activation.
float64 theta_task
float64 theta_base
float64 theta_increment
float64 theta_robot_cmd
float64 theta_robot_fb
bool theta_robot_fb_available

# Axis deviation from the latched reference axis, in degrees.
float64 axis_deviation_cmd_deg
float64 axis_deviation_fb_deg
bool axis_deviation_fb_available

# Dimensionless virtual-object objective terms.
float64 objective_total
float64 objective_rot
float64 objective_conn
float64 objective_axis
float64 objective_pos

uint8 REFINEMENT_NOT_ACTIVE=0
uint8 REFINEMENT_APPLIED=1
uint8 REFINEMENT_FALLBACK_BASELINE=2
uint8 refinement_status

uint8 FAILURE_NONE=0
uint8 FAILURE_ROBOT_REFERENCE_INVALID=1
uint8 FAILURE_HUMAN_REFERENCE_INVALID=2
uint8 FAILURE_HUMAN_GEOMETRY_INVALID=3
uint8 FAILURE_BACKEND_UNAVAILABLE=4
uint8 FAILURE_SOLVER_ERROR=5
uint8 FAILURE_NONFINITE=6
uint8 FAILURE_LIMITS=7
uint8 FAILURE_TRUST_REGION=8
uint8 FAILURE_DEGENERATE_TRIPOD=9
uint8 FAILURE_AXIS_DEVIATION=10
uint8 FAILURE_BASELINE_INCOMPLETE=11
uint8 FAILURE_REFINEMENT_REJECTED=12
uint8 FAILURE_AXIS_MISMATCH=13
uint8 failure_reason

uint32 iterations
uint32 evaluations
float64 solve_duration_sec
