import { writable } from 'svelte/store';
import * as THREE from 'three';

export const splineObject = writable<THREE.Group | undefined>(undefined);

export function setSplineObject(object: THREE.Group | undefined) {
	splineObject.set(object);
}

export function clearSplineObject() {
	splineObject.set(undefined);
}