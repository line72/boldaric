# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# Web Server for the boldaric project
#
# This provides a RESTful API for creating stations, getting next
# tracks for a stations, rating songs, seeding songs, and so on.

import numpy as np


def make_history():
    # !mwd - I don't love how I am doing this
    #  But, we essentially have 148 dimensions:
    #  128 for genres
    #  13 fo mfcc
    #  2 for groove
    #  5 for mood
    #
    # We'll create a list of 148 lists were each list will store the
    #  history a tuple (value, weight) for a specific feature

    return [[] for x in range(148)]


def add_history(history, feature_list, rank):
    # The history is a 148 dimension list of lists
    # Feature list is also 148 dimension
    #  For each dimension, add a tuple of (value, rank)
    assert len(history) == len(feature_list)

    for i, feat in enumerate(feature_list):
        history[i].append((feat, rank))
    return history


def calculate_force(values, attractions, particle_position):
    SIGMA_SQ_2 = 0.005  # 2 * 0.05**2

    # Calculate a new force based upon the points and their
    #  attraction weights around our particle

    distance = values - particle_position
    exp_term = np.exp(-(distance**2) / SIGMA_SQ_2)
    force = attractions * exp_term * np.sign(distance)
    return np.sum(force)


def update_particle_position(
    values, attractions, particle_position, velocity, time_step=0.001, damping=0.99
):
    # Step through our simulation of moving a particle
    force = calculate_force(values, attractions, particle_position)
    acceleration = force
    velocity = velocity * damping + acceleration * time_step
    particle_position += velocity * time_step
    return particle_position, velocity


def run_simulation(points):
    points_array = np.array(points)
    values = points_array[:, 0]
    attractions = points_array[:, 1]
    central_point = np.mean(values)

    # Give the particle just a little bit of randomness in its starting
    #  position
    particle_position = central_point + np.random.uniform(-0.01, 0.01)

    velocity = 0.0
    time_step = 0.001
    total_time = 0.1

    iterations = int(total_time / time_step)
    prev_position = particle_position

    for _ in range(iterations):
        particle_position, velocity = update_particle_position(
            values, attractions, particle_position, velocity, time_step
        )
        # Early stopping if converged
        if abs(particle_position - prev_position) < 1e-6 and abs(velocity) < 1e-6:
            break
        prev_position = particle_position

    return particle_position


def attract(pool, history, chunksize):
    # For all 148 of our feature dimension,
    #  we are going to run a simulation of dropping
    #  a particle near the center of the points in
    #  that feature dimension, and let it bounce around
    #  based upon the attraction of other particles
    # That will give us a new position for each dimension
    #  to use as a similarity
    return list(pool.imap(run_simulation, history, chunksize))
