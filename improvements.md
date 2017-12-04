#MyBot.py October 27, 2017

* action targets closest planet in range
    * IF closest planet is occupied by enemy:
        * Destroy attached enemy ships
    * IF can dock closest planet:
        * Dock
    * IF cannot perform either action:
        * move towards closest unowned planet
        
        
     # TODO don't start docking until no nearby enemies
     # TODO avoid collisions with border
     # TODO defend docked/docking ships
     # TODO target docking ships over docked ships       


     # finished nov 8 - attack docking > docked, and all enemy ships nearby before docking
     # finished nov 8 - attack enemy ships nearby if owned planet is also nearby
     # finished nov 8 - outwardly expanding system for keeping track of nearby ships (see OneNote)