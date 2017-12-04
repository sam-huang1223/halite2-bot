"""
This bot's name is Settler. It's purpose is simple (don't expect it to win complex games :) ):
1. Initialize game
2. If a ship is not docked and there are unowned planets
2.a. Try to Dock in the planet if close enough
2.b If not, go towards the planet

Note: Please do not place print statements here as they are used to communicate with the Halite engine. If you need
to log anything use the logging module.
"""

import hlt
from time import clock

# GAME START
game = hlt.Game("testBot")
# print our start message to the logs

reduced_speed = hlt.constants.MAX_SPEED * 0.8

def order_planets(ship, planets):
    output = []
    for planet in planets:
        output.append([planet, ship.calculate_distance_between(planet)])

    def takeSecond(elem):
        return elem[1]

    return [planet[0] for planet in sorted(output, key=takeSecond)]

while True:
    # TURN START
    startTime = clock()
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()

    # Here we define the set of commands to be sent to the Halite engine at the end of the turn
    command_queue = []

    # For every ship that I control
    for ship in game_map.get_me().all_ships():
        # If the ship is docked
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue

        ordered_planets = order_planets(ship=ship, planets=game_map.all_planets())
        # For each planet in the game (only non-destroyed planets are included)
        for planet in ordered_planets:
            # If the planet is owned
            if planet.is_owned() and planet.owner != game_map.get_me():
                target = planet.all_docked_ships()[0]
                distance_between = max(0, ship.calculate_distance_between(target) - hlt.constants.SHIP_RADIUS - 0.1)
                speed = reduced_speed if distance_between > reduced_speed else distance_between
                navigate_command = ship.navigate(target, game_map,
                speed=speed, ignore_ships=False, ignore_planets=False)
                if navigate_command:
                    command_queue.append(navigate_command)
                    break
            # If we can dock, let's (try to) dock. If two ships try to dock at once, neither will be able to.
            elif ship.can_dock(planet) and planet.owner is None:
                command_queue.append(ship.dock(planet))
                break
            elif not planet.is_owned():
                # If we can't dock, we move towards the closest empty point near this planet (by using closest_point_to)
                # with constant speed. Don't worry about pathfinding for now, as the command will do it for you.
                # We run this navigate command each turn until we arrive to get the latest move.
                # Here we move at half our maximum speed to better control the ships
                # In order to execute faster we also choose to ignore ship collision calculations during navigation.
                # This will mean that you have a higher probability of crashing into ships, but it also means you will
                # make move decisions much quicker. As your skill progresses and your moves turn more optimal you may
                # wish to turn that option off.
                navigate_command = ship.navigate(ship.closest_point_to(planet), game_map, speed=reduced_speed,
                                                 ignore_ships=False, ignore_planets=False)
                # If the move is possible, add it to the command_queue (if there are too many obstacles on the way
                # or we are trapped (or we reached our destination!), navigate_command will return null;
                # don't fret though, we can run the command again the next turn)
                if navigate_command:
                    command_queue.append(navigate_command)
                    break
        endTime = clock()
        if endTime - startTime > 1.9:
            break
    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END


