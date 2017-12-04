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
from math import cos, sin, radians, floor, sqrt
from logging import basicConfig, info, DEBUG
from os.path import exists
from os import remove, mkdir
from time import clock

import turn_functions as Turn
import planet_functions as Planet
import ship_functions as Ship

class Halite2:
    def __init__(self):
        if exists('./game_output.log'):
            remove('./game_output.log')
        if exists('./data/turn_times.csv'):
            remove('./data/turn_times.csv')
        if not exists('./data'):
            mkdir('./data')
        basicConfig(filename='game_output.log', filemode='a', level=DEBUG)

        self.game = hlt.Game("Zerg")
        # print our start message to the logs
        info("Zerg infestation begins")

        self.opponents = {player.id: player for player in self.game.map.all_players() if player != self.game.map.get_me()}

        ### parameters
        self.max_corrections = 9
        self.angular_step = 10
        self.safe_radius = hlt.constants.SHIP_RADIUS + 0.05
        self.scan_range = hlt.constants.MAX_SPEED * 4
        self.scan_radius = sqrt(self.scan_range**2 + self.scan_range**2)
        ###

        ### data collection
        self.turn_counter = 0
        self.turn_times_file = open('./data/turn_times.csv', 'w')
        self.turn_times_file.write('Turn Number,Turn Time\n')
        ###

        self.command_queue = {}

        while True:
            try:
                self.turn()
            except Exception as e:
                info(e)
                raise e

    def turn(self):
        startTime = clock()

        self.turn_counter += 1
        self.game_map = self.game.update_map()
        self.command_queue[self.turn_counter] = []
        self.end_game = (len(self.game_map.get_me().all_ships()) / len(self.game_map._all_ships())) > 0.8

        self.my_ships_x, self.my_ships_y = Turn.update_my_ship_positions(self.game)
        self.enemy_ships_x, self.enemy_ships_y = Turn.update_enemy_ship_positions(self.game)

        def generate(iterator):
            for item in iterator:
                yield item

        ### commands for docked ships
        for planet in [planet for planet in self.game_map.all_planets() if planet.owner == self.game_map.get_me()]:
            nearby_friendly_ships_ids, nearby_enemy_ships_ids = self.update_nearby_entities(planet)
            if nearby_friendly_ships_ids:
                for friendly in nearby_friendly_ships_ids:
                    friendly_ship = self.game_map.get_me().get_ship(friendly)
                    if friendly_ship.docking_status == friendly_ship.DockingStatus.UNDOCKED:
                        break
                else: # if no undocked friendly ship found
                    docked_ships = generate(planet.all_docked_ships())
                    for _ in nearby_enemy_ships_ids:
                        # for every enemy ship near owned planet, undock 2 friendly ships
                        try:
                            fighter1 = next(docked_ships)
                            command = fighter1.undock()
                            self.command_queue[self.turn_counter].append(command)
                            fighter1.action = 'stay'
                            fighter2 = next(docked_ships)
                            command = fighter2.undock()
                            self.command_queue[self.turn_counter].append(command)
                            fighter1.action = 'stay'
                        except StopIteration:
                            break

        for ship in self.game_map.get_me().all_ships():
            if ship.docking_status != ship.DockingStatus.UNDOCKED:
                continue

            ordered_planets = [planet[0] for planet in sorted([
                [planet, ship.calculate_distance_between(planet)] for planet in self.game_map.all_planets()
                                                ], key=lambda x: x[1])]

            # TODO frontload heavy computations in turn 1, (take up to 2s if necessary)

            ##### note all improvements over starter bot
            # TODO NOW avoid collisions at all costs (stay if next move causes crash)
            # TODO collide with enemy if health is lower

            # TODO track power of players and prioritize targeting weaker players/weaker areas (be 2/3 not 4th)
            # TODO (option 1) weighting of weakest/closest planet to be targeted first
            ##### TODO KEY(option 1) advanced 1v1 attack maneuvers - do 1v1 instead of 1v2 (https://halite.io/learn-programming-challenge/basic-game-rules/game-rules-deep-dive)

            ## TODO new option 4??): If destroying enemy ships requires more resources than destroying planet, navigate around ships to destroy planets instead
            # TODO (option 1): target planets with minimal ships rather than more ships (easier to take over)

            command = self.decision(ship, ordered_planets)
            ship.command = command
            self.command_queue[self.turn_counter].append(command)
            if clock() - startTime > 1.8:
                info('Loop broken')
                break

        # TODO use pytest to test velocity's impact on speed of ships given ship.thrust(0,0) command

        self.game.send_command_queue(self.command_queue[self.turn_counter])

        to_be_logged = '{turn},{turn_time}\n'.format(turn=self.turn_counter, turn_time=clock()-startTime)
        info(to_be_logged)
        commands_given = len(self.command_queue[self.turn_counter])
        commandable_ships = len([ship for ship in self.game_map.get_me().all_ships()
                                 if ship.docking_status == ship.DockingStatus.UNDOCKED])
        info('Commands given:')
        info(commands_given)
        info('Commandable ships:')
        info(commandable_ships)

        self.turn_times_file.write(to_be_logged)

    def decision(self, ship, ordered_planets):
        command = None
        nearby_friendly_ships_ids, nearby_enemy_ships_ids = self.update_nearby_entities(ship)
        #### questionable tactic
        if self.end_game:
            if not self.get_nearby_enemy_planets(ship, ordered_planets):
                output = []
                for planet in [planet for planet in self.game_map.all_planets() if
                               (planet.owner != self.game_map.get_me() and planet.owner is not None)]:
                    output.append([planet, ship.calculate_distance_between(planet)])
                ordered_enemy_planets = [planet[0] for planet in sorted(output, key=lambda x: x[1])]
                if ordered_enemy_planets:
                    ship.target = ordered_enemy_planets[0]
                    ship.action = 'travel'
                    command = self.navigate(ship, ship.target, ship.target, self.game_map,
                                            hlt.constants.MAX_SPEED, self.max_corrections, self.angular_step,
                                            nearby_friendly_ships_ids)

        # feature for tomorrow - undock if enemy ship nearby + no friendly undocked ships nearby
        # finished today - attack docking > docked, and all enemy ships nearby before docking
        # finished today - attack enemy ships nearby if owned planet is also nearby
        # finished today - outwardly expanding system for keeping track of nearby ships (see OneNote)

        ### planet-independent commands
        else:
            if nearby_enemy_ships_ids and self.check_for_nearby_owned_planets(ship, ordered_planets):
                # if there are enemies near an owned planet, attack them
                target_id = nearby_enemy_ships_ids[0]
                ship.target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                command = self.attack(ship, ship.target, nearby_friendly_ships_ids)
            # TODO find way to keep track of production of enemy planets to check if new ships are coming out??
            ### planet-dependent commands
            else:
                for planet in ordered_planets:
                    if planet.owner in self.opponents.values():
                        for ship_id in nearby_enemy_ships_ids:
                            enemy_ship = self.game_map.get_player(ship_id[1]).get_ship(ship_id[0])
                            if enemy_ship.docking_status == enemy_ship.DockingStatus.DOCKING and enemy_ship.planet == planet:
                                ship.target = enemy_ship
                                break
                        if not ship.target:
                            ship.target = planet.all_docked_ships()[0]
                            # target closest enemy ship if no docking enemy ships found
                        command = self.attack(ship, ship.target, nearby_friendly_ships_ids)
                        break

                    # If we can dock, let's (try to) dock. If two ships try to dock at once, neither will be able to.
                    elif not planet.is_full():  # can_dock only checks distance not capacity, use is_full to check capacity
                        if nearby_enemy_ships_ids:
                            # TODO only pursue if hp is higher, otherwise collide if approaching, mine if not approaching
                            target_id = nearby_enemy_ships_ids[0]
                            target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                            if target.docking_status == target.DockingStatus.UNDOCKED:
                                ship.target = target
                                command = self.attack(ship, ship.target, nearby_friendly_ships_ids)
                                break

                        if ship.can_dock(planet):
                            ship.target = planet
                            ship.action = 'stay'
                            command = ship.dock(planet)
                            break

                        # check commands_tracker to see which planets other ships are heading to
                        if Planet.check_if_planet_will_have_space(self.game_map.get_me().all_ships(), planet,
                                                                  docked_tracker={planet: len(planet.all_docked_ships())
                                                                                  for planet in self.game_map.all_planets()}):
                            ship.target = planet
                            if ship.can_dock(planet):
                                ship.action = 'stay'
                                command = ship.dock(planet)
                            else:
                                ship.action = 'travel'
                                command = self.navigate(ship, planet, planet, self.game_map,
                                        hlt.constants.MAX_SPEED, self.max_corrections, self.angular_step, nearby_friendly_ships_ids)
                            break

            ## TODO put cap on max number of ships chasing 1 enemy
            ## TODO in more than 2 players -> expand outwards
            ## TODO prioritize establishing position away from other players
            ## TODO prioritize targeting weaker players when attacking

        if not command:
            if nearby_enemy_ships_ids:
                target_id = nearby_enemy_ships_ids[0]
                ship.target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                command = self.attack(ship, ship.target, nearby_friendly_ships_ids)
            else:
                for planet in ordered_planets:
                    if planet.owner in self.opponents.values():
                        enemy_docked_ships = planet.all_docked_ships()
                        if enemy_docked_ships:
                            ship.target = enemy_docked_ships[0]
                            command = self.attack(ship, ship.target, nearby_friendly_ships_ids)
                            break
                    elif planet.owner is None:
                        ship.target = planet
                        if ship.can_dock(planet):
                            ship.action = 'stay'
                            command = ship.dock(planet)
                        else:
                            ship.action = 'travel'
                            command = self.navigate(ship, ship.target, ship.target,
                                                self.game_map, hlt.constants.MAX_SPEED, self.max_corrections,
                                                self.angular_step, nearby_friendly_ships_ids)
                        break
        if not command:
            ship.action = 'stay'
            # TODO maybe have stay counteract effects of previous velocity?
            return ship.thrust(magnitude=0, angle=0)
        else:
            return command

    def attack(self, ship, target, nearby_friendly_ships_ids):
        ship.action = 'attack'
        distance_between = max(0, ship.calculate_distance_between(target) - hlt.constants.WEAPON_RADIUS + 1)
        speed = hlt.constants.MAX_SPEED if distance_between > hlt.constants.MAX_SPEED else distance_between
        return self.navigate(ship, target, target, self.game_map, speed, self.max_corrections,
                             self.angular_step, nearby_friendly_ships_ids)

    def check_for_nearby_owned_planets(self, ship, ordered_planets):
        for planet in ordered_planets:
            if planet.owner != self.game_map.get_me():
                continue
            distance = ship.calculate_distance_between(planet)
            if distance < self.scan_radius:
                return True
        return False

    def get_nearby_enemy_planets(self, ship, ordered_planets):
        nearby_enemy_planets = []
        for planet in ordered_planets:
            if planet.owner != self.game_map.get_me():
                distance = ship.calculate_distance_between(planet)
                if distance > self.scan_radius:
                    break
                nearby_enemy_planets.append(planet)
        return nearby_enemy_planets

    def check_friendly_collisions(self, ship, speed, angle, nearby_friendly_ships_ids):
        def check_intersect(A, B, C, D):
            # Return true if line segments AB and CD intersect
            def ccw(A, B, C):
                return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)
            if (ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)) or (B.x == D.x and B.y == D.y):
                # also check if end points are an intersection (no need to check start points)
                return True
            return False

        ### these functions are used to check if a line and point intersect (docking ship collisions)
        def check_stationary_friendly(ship, friendly_ship, ship_target):
            if hlt.collision.intersect_segment_circle(start=ship, end=ship_target, circle=friendly_ship, fudge=0.05):
                return True

            ship_dx = cos(angle) * self.safe_radius
            ship_dy = sin(angle) * self.safe_radius
            ship.x += ship_dx
            ship.y += ship_dy

            ship_target_angle = ship_target.calculate_angle_between(ship)
            ship_target_dx = cos(ship_target_angle) * self.safe_radius
            ship_target_dy = sin(ship_target_angle) * self.safe_radius
            ship_target.x += ship_target_dx
            ship_target.y += ship_target_dy

            if hlt.collision.intersect_segment_circle(start=ship, end=ship_target, circle=friendly_ship, fudge=0.05):
                return True

            ship.x -= 2 * ship_dx
            ship.y -= 2 * ship_dy
            ship_target.x -= 2 * ship_target_dx
            ship_target.y -= 2 * ship_target_dy

            if hlt.collision.intersect_segment_circle(start=ship, end=ship_target, circle=friendly_ship, fudge=0.05):
                return True

            return False

        # check if upper boundary (+0.5) intersects, and if lower boundary (-0.5) intersects
        for friendly in nearby_friendly_ships_ids:
            friendly_ship = self.game_map.get_me().get_ship(friendly)
            ship_target = Ship.calculate_endpoint(ship, speed, angle)

            if friendly_ship.docking_status != friendly_ship.DockingStatus.UNDOCKED:
                return check_stationary_friendly(ship, friendly_ship, ship_target)

            if friendly_ship.command is None:
                continue
            elif friendly_ship.action == 'stay':
                return check_stationary_friendly(ship, friendly_ship, ship_target)

            friendly_ship_command = friendly_ship.command.split()

            if friendly_ship_command[0] == 'd':
                return check_stationary_friendly(ship, friendly_ship, ship_target)

            friendly_ship_target = Ship.calculate_endpoint(ship=friendly_ship,
                                                      speed=int(friendly_ship_command[2]),
                                                      angle=int(friendly_ship_command[3]))

            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

            # problem here - figure out how to calculate dynamic value for ship.y += ???
            # next - put cap on max number of ships chasing 1 enemy - 2 max/per
            # next - advanced fighting tactics (draw ships into allied ships)

            ship_dx = cos(angle) * self.safe_radius
            ship_dy = sin(angle) * self.safe_radius
            ship.x += ship_dx
            ship.y += ship_dy

            ship_target_angle = ship_target.calculate_angle_between(ship)
            ship_target_dx = cos(ship_target_angle) * self.safe_radius
            ship_target_dy = sin(ship_target_angle) * self.safe_radius
            ship_target.x += ship_target_dx
            ship_target.y += ship_target_dy

            friendly_ship_angle = friendly_ship.calculate_angle_between(friendly_ship_target)
            friendly_ship_dx = cos(friendly_ship_angle) * self.safe_radius
            friendly_ship_dy = sin(friendly_ship_angle) * self.safe_radius
            friendly_ship.x += friendly_ship_dx
            friendly_ship.y += friendly_ship_dy

            friendly_ship_target_angle = friendly_ship_target.calculate_angle_between(friendly_ship)
            friendly_ship_target_dx = cos(friendly_ship_target_angle) * self.safe_radius
            friendly_ship_target_dy = sin(friendly_ship_target_angle) * self.safe_radius
            friendly_ship_target.x += friendly_ship_target_dx
            friendly_ship_target.y += friendly_ship_target_dy

            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

            ship.x -= 2*ship_dx
            ship.y -= 2*ship_dy
            ship_target.x -= 2*ship_target_dx
            ship_target.y -= 2*ship_target_dy
            friendly_ship.x -= 2*friendly_ship_dx
            friendly_ship.y -= 2*friendly_ship_dy
            friendly_ship_target.x -= 2*friendly_ship_target_dx
            friendly_ship_target.y -= 2*friendly_ship_target_dy

            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

            ship.x += 2 * ship_dx
            ship.y += 2 * ship_dy
            ship_target.x += 2 * ship_target_dx
            ship_target.y += 2 * ship_target_dy

            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

            ship.x -= 2 * ship_dx
            ship.y -= 2 * ship_dy
            ship_target.x -= 2 * ship_target_dx
            ship_target.y -= 2 * ship_target_dy
            friendly_ship.x += 2 * friendly_ship_dx
            friendly_ship.y += 2 * friendly_ship_dy
            friendly_ship_target.x += 2 * friendly_ship_target_dx
            friendly_ship_target.y += 2 * friendly_ship_target_dy

            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

        return False

    def navigate(self, ship, target, original_target, game_map, speed, max_corrections, angular_step, nearby_friendly_ships_ids):
        if max_corrections <= 0:
            if angular_step < 0:
                return None
            else:
                return self.navigate(ship, original_target, original_target, game_map, speed, self.max_corrections, -angular_step, nearby_friendly_ships_ids)
        distance = ship.calculate_distance_between(target) - target.radius
        if distance > hlt.constants.MAX_SPEED:
            target = ship.closest_point_to(target, min_distance=speed)

        angle = ship.calculate_angle_between(target)

        new_target_dx = cos(radians(angle + angular_step)) * distance
        new_target_dy = sin(radians(angle + angular_step)) * distance

        adjust_condition = (game_map.obstacles_between(ship, target) or
                            #self.check_friendly_collisions(ship, speed, angle, nearby_friendly_ships_ids) or
                           (ship.x + new_target_dx) >= self.game_map.width or (ship.x + new_target_dx) <= 0 or
                           (ship.y + new_target_dy) >= self.game_map.height or (ship.y + new_target_dy) <= 0)
        if adjust_condition:
            new_target = hlt.entity.Position(ship.x + new_target_dx, ship.y + new_target_dy)
            return self.navigate(ship, new_target, original_target, game_map, speed, max_corrections - 1, angular_step, nearby_friendly_ships_ids)
        speed = speed if (distance >= speed) else distance
        return ship.thrust(speed, angle)

    def update_nearby_entities(self, entity):
        nearby_enemy_ships_ids = []
        nearby_friendly_ships_ids = []

        if type(entity) == hlt.entity.Planet:
            scan_range = self.scan_range-hlt.constants.MAX_SPEED
        elif type(entity) == hlt.entity.Ship:
            scan_range = self.scan_range

        for n in range(1, scan_range):
            if floor(entity.x + n) < self.game_map.width:
                for dy in range(-n, n + 1):
                    try:
                        possible_enemy_ship = set.intersection(
                            self.enemy_ships_x[floor(entity.x + n)],
                            self.enemy_ships_y[floor(entity.y + dy)]
                        )
                        if possible_enemy_ship:
                            nearby_enemy_ships_ids.append(list(possible_enemy_ship)[0])
                    except KeyError:
                        continue

                    try:
                        possible_friendly_ship = set.intersection(
                            self.my_ships_x[floor(entity.x + n)],
                            self.my_ships_y[floor(entity.y + dy)]
                        )
                        if possible_friendly_ship:
                            nearby_friendly_ships_ids.append(list(possible_friendly_ship)[0])
                    except KeyError:
                        continue
            if floor(entity.x - n) >= 0:
                for dy in range(-n, n + 1):
                    try:
                        possible_enemy_ship = set.intersection(
                            self.enemy_ships_x[floor(entity.x - n)],
                            self.enemy_ships_y[floor(entity.y + dy)]
                        )
                        if possible_enemy_ship:
                            nearby_enemy_ships_ids.append(list(possible_enemy_ship)[0])
                    except KeyError:
                        continue

                    try:
                        possible_friendly_ship = set.intersection(
                            self.my_ships_x[floor(entity.x - n)],
                            self.my_ships_y[floor(entity.y + dy)]
                        )
                        if possible_friendly_ship:
                            nearby_friendly_ships_ids.append(list(possible_friendly_ship)[0])
                    except KeyError:
                        continue

            if floor(entity.y + n) < self.game_map.height:
                for dx in range(-n + 1, n):
                    try:
                        possible_enemy_ship = set.intersection(
                            self.enemy_ships_x[floor(entity.x + dx)],
                            self.enemy_ships_y[floor(entity.y + n)]
                        )
                        if possible_enemy_ship:
                            nearby_enemy_ships_ids.append(list(possible_enemy_ship)[0])
                    except KeyError:
                        continue

                    try:
                        possible_friendly_ship = set.intersection(
                            self.my_ships_x[floor(entity.x + dx)],
                            self.my_ships_y[floor(entity.y + n)]
                        )
                        if possible_friendly_ship:
                            nearby_friendly_ships_ids.append(list(possible_friendly_ship)[0])
                    except KeyError:
                        continue

            if floor(entity.y - n) >= 0:
                for dx in range(-n + 1, n):
                    try:
                        possible_enemy_ship = set.intersection(
                            self.enemy_ships_x[floor(entity.x + dx)],
                            self.enemy_ships_y[floor(entity.y - n)]
                        )
                        if possible_enemy_ship:
                            nearby_enemy_ships_ids.append(list(possible_enemy_ship)[0])
                    except KeyError:
                        continue

                    try:
                        possible_friendly_ship = set.intersection(
                            self.my_ships_x[floor(entity.x + dx)],
                            self.my_ships_y[floor(entity.y - n)]
                        )
                        if possible_friendly_ship:
                            nearby_friendly_ships_ids.append(list(possible_friendly_ship)[0])
                    except KeyError:
                        continue
        return nearby_friendly_ships_ids, nearby_enemy_ships_ids

Halite2()

