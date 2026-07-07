import { writable } from 'svelte/store';
import type { EulerPose } from '$lib/types';

export const currentTrajectory = writable<EulerPose[]>(
    [
        {position: [0, 0, 0], orientation: [0, 0, 0]},
        {position: [-0.5, 0.5, 0.5], orientation: [0, 0, 0]}
    ]
);