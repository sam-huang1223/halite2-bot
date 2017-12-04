from math import floor

def update_my_ship_positions(game):
    my_ships_x = {x: set() for x in range(game.map.width)}
    my_ships_y = {y: set() for y in range(game.map.height)}

    for ship in game.map.get_me().all_ships():
        my_ships_x[floor(ship.x)].add(ship.id)
        my_ships_y[floor(ship.y)].add(ship.id)

    return my_ships_x, my_ships_y


def update_enemy_ship_positions(game):
    enemy_ships_x = {x: set() for x in range(game.map.width)}
    enemy_ships_y = {y: set() for y in range(game.map.height)}

    all_enemy_ships = [ship for ship in game.map._all_ships() if
                       ship not in game.map.get_me().all_ships()]

    for ship in all_enemy_ships:
        enemy_ships_x[floor(ship.x)].add((ship.id, ship.owner.id))
        enemy_ships_y[floor(ship.y)].add((ship.id, ship.owner.id))

    return enemy_ships_x, enemy_ships_y