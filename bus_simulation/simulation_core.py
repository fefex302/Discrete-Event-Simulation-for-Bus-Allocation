import simpy
import random


# Bus class representing a bus in the simulation
class Bus:
    def __init__(self, env, name, capacity):
        self.env = env
        self.name = name
        self.travels = 0  # Counter for the number of trips made
        self.capacity = capacity # Maximum number of passengers this bus can carry
        self.passengers_on_board = 0 # Counter for passengers currently on board
        self.traveling = False # Indicates if the bus is currently traveling

# Participant class representing a client in the simulation
class Participant:
    def __init__(self, env, name, time_arrival):
        self.env = env
        self.name = name
        self.time_arrival = time_arrival # Time when the client arrived at the bus stop
        self.time_boarded = None  # Time when the client boarded the bus
        self.time_departure = None  # Time when the client finished their journey (simplified)

# Used to store the configuration of the simulation
class Configuration:
    def __init__(self, num_navette, smart_driver, smart_time, smart_percentage, smart_last_boarding_time, max_passengers):
        self.num_navette = num_navette
        self.smart_driver = smart_driver # Indicates if the bus driver is smart
        self.smart_time = smart_time # Time the bus can wait before deciding to leave
        self.smart_percentage = smart_percentage # Percentage of bus capacity that must be filled before the bus departs
        self.smart_last_boarding_time = smart_last_boarding_time # Maximum time since the last boarding before the bus decides to leave
        self.max_passengers = max_passengers  # Maximum number of passengers for this configuration
        self.history = []  # List to keep track of passengers and their boarding and disembarking times

# Function to generate participants (people to be boarded) in the simulation
def participant_generator(env, passenger_queue, history, tempo_massimo_simulazione, MAX_PASSENGERS, PEAK_HOUR, BASE_LAMBDA, PEAK_FACTOR, verbose = False):
    i = 0
    while len(history) < MAX_PASSENGERS:  # Limit the number of clients to MAX_PASSENGERS
        now = int(env.now)
        if now < PEAK_HOUR:
            new_lambda = BASE_LAMBDA + PEAK_FACTOR * (now / PEAK_HOUR)**2
        else:
            new_lambda = BASE_LAMBDA + PEAK_FACTOR

        # Generate a new participant based on the adjusted arrival rate
        yield env.timeout(random.expovariate(new_lambda))
        i += 1
        if verbose:
            print(f'{env.now:.2f}: Participant {i} arrives and joins general queue.')

        # Participants join a general queue, not looking for a specific bus right away
        passenger = Participant(env, i, env.now)
        history.append(passenger)  # Add the participant to history for final report

        passenger_queue.put(passenger)
        if env.now > tempo_massimo_simulazione: 
            break

# def participant(env, passenger, bus_destination):
#     yield env.timeout(0)
#     print(f'{env.now:.2f}: passenger {passenger.name} has boarded {bus_destination.name}.')
#     # The client's action ends here for this simulation, but could include the journey and disembarkation

def bus_process(env, bus_obj, bus_attivi_per_imbarco, passenger_queue, SMART_DRIVER, SMART_TIME, SMART_PERCENTAGE, TRAVEL_TIME_MEAN, TRAVEL_TIME_STD, HYBRID = False, HYBRID_TIME=125, verbose = False, TIME_FROM_LAST_BOARDING=2):
    # Bus cycle
    smart_driver = SMART_DRIVER  # Local copy of SMART_DRIVER to allow dynamic changes
    while True:
        # The bus tries to put itself in the active boarding queue
        yield bus_attivi_per_imbarco.put(bus_obj)
        if HYBRID:
            if env.now >= HYBRID_TIME:
                smart_driver = False
                if verbose:
                    print(f'{env.now:.2f}: {bus_obj.name} switches to non-smart driving.')    

        # After being put in the queue, the bus can board passengers
        if verbose:
            print(f'\n{env.now:.2f}: {bus_obj.name} is at the stop and active for boarding.')

        bus_obj.passengers_on_board = 0 # Counter for passengers on board
        current_passengers = [] # A list to keep track of current passengers boarding this bus
        time_idle = env.now  # Time when the bus started waiting for passengers
        time_from_last_boarding = 0  # Time since the last boarding
        time_of_last_boarding = env.now # Time of the last boarding action

        # # The bus will board passengers until it is full or the SMART_DRIVER conditions are met
        while bus_obj.passengers_on_board < bus_obj.capacity and (not smart_driver or (env.now - time_idle <= SMART_TIME and bus_obj.passengers_on_board <= bus_obj.capacity * SMART_PERCENTAGE)
                                                                                     or (env.now - time_idle <= SMART_TIME and time_from_last_boarding < TIME_FROM_LAST_BOARDING)
                                                                                     ):        
        # while bus_obj.passengers_on_board < bus_obj.capacity and (not smart_driver or (env.now - time_idle <= SMART_TIME and bus_obj.passengers_on_board <= bus_obj.capacity * SMART_PERCENTAGE)
        #                                                                              or (env.now - time_idle <= SMART_TIME and time_from_last_boarding < TIME_FROM_LAST_BOARDING)
        #                                                                              or (bus_obj.passengers_on_board <= bus_obj.capacity * SMART_PERCENTAGE <= SMART_TIME and time_from_last_boarding < TIME_FROM_LAST_BOARDING)):
        # while bus_obj.passengers_on_board < bus_obj.capacity and (not smart_driver or (env.now - time_idle <= SMART_TIME
        #                                                                                        and bus_obj.passengers_on_board <= bus_obj.capacity * SMART_PERCENTAGE
        #                                                                                        and time_from_last_boarding < TIME_FROM_LAST_BOARDING)):
            # Wait for a passenger to be available in the queue
            passenger = yield passenger_queue.get()
            current_passengers.append(passenger)

            # update the frequency of boarding
            if smart_driver:
                time_from_last_boarding = env.now - time_of_last_boarding
                time_of_last_boarding = env.now

            # Once a passenger is available, board them on THIS bus
            #env.process(client(env, passenger, bus_obj))
            passenger.time_boarded = env.now  # Record the time the passenger boarded the bus
            bus_obj.passengers_on_board += 1

            if verbose:
                print(f'{env.now:.2f}: {bus_obj.name}: boarded passenger {passenger.name}. Total: {bus_obj.passengers_on_board}/{bus_obj.capacity}.')

        bus_obj.travels += 1
        if verbose:
            print(f'{env.now:.2f}: {bus_obj.name} is full ({bus_obj.passengers_on_board} passengers). now departing!')

        for passenger in current_passengers:
            passenger.time_departure = env.now

        # Once full, the bus "removes itself" from the active boarding bus store
        # This allows the next bus in line to activate.
        yield bus_attivi_per_imbarco.get() # The bus removes itself from the "active for boarding" state

        # Simulate the journey
        bus_obj.traveling = True
        travel_time = max(0, random.gauss(TRAVEL_TIME_MEAN, TRAVEL_TIME_STD))
        yield env.timeout(travel_time)
        bus_obj.traveling = False

        if verbose:
            print(f'{env.now:.2f}: {bus_obj.name} has arrived at destination and is unloading passengers. Now returning empty.')
        bus_obj.passengers_on_board = 0 # Unload passengers
        # The bus is now available for the next cycle (will return to boarding queue)