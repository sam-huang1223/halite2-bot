from math import cos, sin, radians
import hlt

def calculate_endpoint(ship, speed, angle):
    new_target_dx = cos(radians(angle)) * speed
    new_target_dy = sin(radians(angle)) * speed
    return hlt.entity.Position(x=ship.x + new_target_dx, y=ship.y + new_target_dy)