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
from math import cos, sin, radians, floor, isclose, sqrt
from logging import basicConfig, info, DEBUG
from os.path import exists
from os import remove, mkdir
from time import clock

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
        # TODO order of changes - 1. ship attributes, 2. use self.endGame instead of calculating every ship iteration

        self.turn_counter += 1
        self.game_map = self.game.update_map()
        self.command_queue[self.turn_counter] = []
        self.endGame = len(self.game_map.get_me().all_ships())/len(self.game_map._all_ships()) > 0.8
        # TODO switch this to be based on planets instead of ships

        self.update_my_ship_positions()
        self.update_enemy_ship_positions()

        staticEndTime = clock()

        def generate(iterator):
            for item in iterator:
                yield item

        ### commands for docked ships
        for planet in [planet for planet in self.game_map.all_planets() if planet.owner == self.game_map.get_me()]:
            nearby_friendly_ships_ids, nearby_enemy_ships_ids = self.update_nearby_entities(planet)
            for friendly in nearby_friendly_ships_ids:
                friendly_ship = self.game_map.get_me().get_ship(friendly)
                if friendly_ship.docking_status == friendly_ship.DockingStatus.UNDOCKED:
                    break
            else:  # if no undocked friendly ship found
                docked_ships = generate(planet.all_docked_ships())
                for _ in nearby_enemy_ships_ids:
                    # for every enemy ship near owned planet, undock 2 friendly ships
                    try:
                        fighter1 = next(docked_ships)
                        fighter1.target = planet
                        fighter1.action = 'stay'
                        command = fighter1.undock()
                        self.command_queue[self.turn_counter].append(command)

                        fighter2 = next(docked_ships)
                        fighter2.target = planet
                        fighter2.action = 'stay'
                        command = fighter2.undock()
                        self.command_queue[self.turn_counter].append(command)
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

            decision = self.decision(ship, ordered_planets)

            if not decision:
                closest_enemy = None
                for planet in ordered_planets:
                    if planet.owner in self.opponents.values():
                        closest_enemy = planet
                        break
                if closest_enemy:
                    if closest_enemy.all_docked_ships():
                        target = closest_enemy.all_docked_ships()[0]
                        decision = self.attack(ship, target, nearby_friendly_ships_ids)
                else:
                    for planet in ordered_planets:
                        if planet.owner is None:
                            target = ship.closest_point_to(planet)
                            decision = self.navigate(ship, target, target, self.game_map,
                                                 hlt.constants.MAX_SPEED, self.max_corrections,
                                                 self.angular_step, nearby_friendly_ships_ids)
            if not decision:
                # TODO maybe have stay counteract effects of previous velocity?
                ship.action = 'stay'
                decision = ship.thrust(magnitude=0, angle=0)

            self.command_queue[self.turn_counter].append(decision)
            ship.command = decision

            if clock() - startTime > 1.8:
                info('Loop broken')
                break

        self.game.send_command_queue(self.command_queue[self.turn_counter])

        to_be_logged = '{turn},{turn_time},static time: {staticTime}\n'.format(turn=self.turn_counter, turn_time=clock()-startTime,
                                                                               staticTime = staticEndTime-startTime)
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
        nearby_friendly_ships_ids, nearby_enemy_ships_ids = self.update_nearby_entities(ship)

        # TODO avoid stay issue, get rid of friendly collisions
        if self.endGame:
            # TODO command -> ship.command
            if nearby_enemy_ships_ids:
                target_id = nearby_enemy_ships_ids[0]
                ship.target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                return self.attack(ship, ship.target, nearby_friendly_ships_ids)

            nearby_dockable_planets = self.get_nearby_dockable_planets(ship, ordered_planets)
            for planet in nearby_dockable_planets:
                if not planet.is_full():
                    ship.target = planet
                    if ship.can_dock(planet):
                        ship.action = 'stay'
                        return ship.dock(planet)
                    else:
                        ship.action = 'travel'
                        return self.navigate(ship, ship.target, ship.target, self.game_map,
                                                hlt.constants.MAX_SPEED, self.max_corrections, self.angular_step,
                                                nearby_friendly_ships_ids)

            nearby_enemy_planets = self.get_nearby_enemy_planets(ship, ordered_planets)
            if not nearby_enemy_planets:
                output = []
                for planet in [planet for planet in self.game_map.all_planets() if
                               (planet.owner != self.game_map.get_me() and planet.owner is not None)]:
                    output.append([planet, ship.calculate_distance_between(planet)])
                ordered_enemy_planets = [planet[0] for planet in sorted(output, key=lambda x: x[1])]
                if ordered_enemy_planets:
                    ship.target = ordered_enemy_planets[0]
                    return self.navigate(ship, ship.target, ship.target, self.game_map,
                                            hlt.constants.MAX_SPEED, self.max_corrections, self.angular_step,
                                            nearby_friendly_ships_ids)
            else:
                ship.target = nearby_enemy_planets[0]
                return self.navigate(ship, ship.target, ship.target, self.game_map,
                                        hlt.constants.MAX_SPEED, self.max_corrections, self.angular_step,
                                        nearby_friendly_ships_ids)

        # feature for tomorrow - undock if enemy ship nearby + no friendly undocked ships nearby
        # finished today - attack docking > docked, and all enemy ships nearby before docking
        # finished today - attack enemy ships nearby if owned planet is also nearby
        # finished today - outwardly expanding system for keeping track of nearby ships (see OneNote)

        ### planet-independent commands
        #nearby_enemy_planets = self.get_nearby_enemy_planets(ship, ordered_planets)
        else:
            if nearby_enemy_ships_ids and self.check_for_nearby_owned_planets(ship, ordered_planets):
                # if there are enemies near an owned planet, attack them

                target_id = nearby_enemy_ships_ids[0]
                target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                return self.attack(ship, target, nearby_friendly_ships_ids)

            #elif nearby_enemy_planets:
            #   pass
            # TODO find way to keep track of production of enemy planets to check if new ships are coming out??
            ###

            ### planet-dependent commands
            else:
                for planet in ordered_planets:
                    if planet.owner in self.opponents.values():
                        for ship_id in nearby_enemy_ships_ids:
                            enemy_ship = self.game_map.get_player(ship_id[1]).get_ship(ship_id[0])
                            if enemy_ship.docking_status == enemy_ship.DockingStatus.DOCKING and enemy_ship.planet == planet:
                                ship.target = enemy_ship
                        if ship.target:
                            target_id = nearby_enemy_ships_ids[0]
                            ship.target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                            # target closest enemy ship if no docking enemy ships found
                        return self.attack(ship, ship.target, nearby_friendly_ships_ids)

                    # If we can dock, let's (try to) dock. If two ships try to dock at once, neither will be able to.
                    elif not planet.is_full():  # can_dock only checks distance not capacity, use is_full to check capacity
                        # TODO only pursue if hp is higher, otherwise collide if approaching, mine if not approaching
                        if nearby_enemy_ships_ids:
                            target_id = nearby_enemy_ships_ids[0]
                            target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
                            return self.attack(ship, target, nearby_friendly_ships_ids)

                        # check commands_tracker to see which planets other ships are heading to
                        elif self.check_if_planet_will_have_space(self.game_map.get_me().all_ships(), planet,
                                                                  docked_tracker={planet: len(planet.all_docked_ships())
                                                                                  for planet in self.game_map.all_planets()}):
                            ship.target = planet
                            if ship.can_dock(planet):
                                ship.action = 'stay'
                                return ship.dock(planet)
                            else:
                                ship.action = 'travel'
                                return self.navigate(ship, ship.target, ship.target, self.game_map,
                                        hlt.constants.MAX_SPEED, self.max_corrections, self.angular_step, nearby_friendly_ships_ids)

        ## TODO prioritize establishing position away from other players
        ## TODO prioritize targeting weaker players when attacking
        ## TODO put cap on max number of ships chasing 1 enemy
        ## TODO in more than 2 players -> expand outwards
        ## TODO attack instead of mine only if enemy ship is approaching (i.e. not docking)

        if nearby_enemy_ships_ids:
            target_id = nearby_enemy_ships_ids[0]
            target = self.game_map.get_player(target_id[1]).get_ship(target_id[0])
            return self.attack(ship, target, nearby_friendly_ships_ids)

    def attack(self, ship, target, nearby_friendly_ships_ids):
        ship.action = 'attack'
        distance_between = max(0, ship.calculate_distance_between(target) - hlt.constants.WEAPON_RADIUS + 1)
        speed = hlt.constants.MAX_SPEED if distance_between > hlt.constants.MAX_SPEED else distance_between
        return self.navigate(ship, target, target, self.game_map, speed, self.max_corrections,
                             self.angular_step, nearby_friendly_ships_ids)

    def check_if_planet_will_have_space(self, ships, planet, docked_tracker):
        count = 0
        for ship in ships:
            if ship.action != 'attack' and ship.target == planet:
                count += 1
        return (count + docked_tracker[planet]) < planet.num_docking_spots

    def calculate_endpoint(self, ship, speed, angle):
        new_target_dx = cos(radians(angle)) * speed
        new_target_dy = sin(radians(angle)) * speed
        return hlt.entity.Position(x=ship.x+new_target_dx, y=ship.y+new_target_dy)

    def check_for_nearby_owned_planets(self, ship, ordered_planets):
        for planet in ordered_planets:
            if planet.owner != self.game_map.get_me():
                continue
            distance = ship.calculate_distance_between(planet)
            if distance < self.scan_radius:
                return True
        return False

    def get_nearby_dockable_planets(self, ship, ordered_planets):
        l = []
        for planet in ordered_planets:
            if planet.owner not in self.opponents.values():
                distance = ship.calculate_distance_between(planet)
                if distance > self.scan_radius:
                    break
                l.append(planet)
        return l

    def get_nearby_enemy_planets(self, ship, ordered_planets):
        nearby_enemy_planets = []
        for planet in ordered_planets:
            if planet.owner in self.opponents.values():
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
            def distance(a, b):
                return sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)

            def is_between(a, c, b):
                # check if c lies between a and b
                return isclose(distance(a, c) + distance(c, b), distance(a, b))

            if is_between(a=ship, c=friendly_ship, b=ship_target):
                return True

            ship.y += 0.55
            ship_target.y += 0.55
            if is_between(a=ship, c=friendly_ship, b=ship_target):
                return True
            ship.y -= 1.1
            ship_target.y -= 1.1
            if is_between(a=ship, c=friendly_ship, b=ship_target):
                return True

            return False

        # check if upper boundary (+0.5) intersects, and if lower boundary (-0.5) intersects
        for friendly in nearby_friendly_ships_ids:
            friendly_ship = self.game_map.get_me().get_ship(friendly)
            ship_target = self.calculate_endpoint(ship, speed, angle)

            if friendly_ship.docking_status != friendly_ship.DockingStatus.UNDOCKED:
                return check_stationary_friendly(ship, friendly_ship, ship_target)

            if not friendly_ship.command:
                continue
            elif friendly_ship.action == 'stay':
                return check_stationary_friendly(ship, friendly_ship, ship_target)

            friendly_ship_command = friendly_ship.command.split()
            if friendly_ship_command[0] == 'd':
                return check_stationary_friendly(ship, friendly_ship, ship_target)

            friendly_ship_target = self.calculate_endpoint(ship=friendly_ship,
                                                      speed=int(friendly_ship_command[2]),
                                                      angle=int(friendly_ship_command[3]))

            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True


            ship.y += 0.55
            ship_target.y += 0.55
            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

            ship.y -= 1.1
            ship_target.y -= 1.1
            if check_intersect(A=ship, B=ship_target, C=friendly_ship, D=friendly_ship_target):
                return True

        return False

    def navigate(self, ship, target, original_target, game_map, speed, max_corrections, angular_step, nearby_friendly_ships_ids):
        if max_corrections <= 0:
            if angular_step < 0:
                return None
            else:
                return self.navigate(ship, original_target, original_target, game_map, speed, self.max_corrections, -angular_step, nearby_friendly_ships_ids)
        distance = ship.calculate_distance_between(target)
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


    def update_my_ship_positions(self):
        self.my_ships_x = {x: set() for x in range(self.game.map.width)}
        self.my_ships_y = {y: set() for y in range(self.game.map.height)}

        for ship in self.game_map.get_me().all_ships():
            self.my_ships_x[floor(ship.x)].add(ship.id)
            self.my_ships_y[floor(ship.y)].add(ship.id)

    def update_enemy_ship_positions(self):
        self.enemy_ships_x = {x: set() for x in range(self.game.map.width)}
        self.enemy_ships_y = {y: set() for y in range(self.game.map.height)}

        self.all_enemy_ships = [ship for ship in self.game_map._all_ships() if ship not in self.game_map.get_me().all_ships()]

        for ship in self.all_enemy_ships:
            self.enemy_ships_x[floor(ship.x)].add((ship.id, ship.owner.id))
            self.enemy_ships_y[floor(ship.y)].add((ship.id, ship.owner.id))

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

