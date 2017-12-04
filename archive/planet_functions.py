def check_if_planet_will_have_space(myShips, planet, docked_tracker):
    count = 0
    for ship in myShips:
        if ship.action != 'attack' and ship.target == planet:
            count += 1
    return (count + docked_tracker[planet]) < planet.num_docking_spots