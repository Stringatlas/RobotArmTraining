export type Vec3 = [number, number, number];

function toVec3(value: readonly number[] | Vec3): Vec3 {
	const x = value[0] ?? 0;
	const y = value[1] ?? 0;
	const z = value[2] ?? 0;
	return [Number(x), Number(y), Number(z)];
}

function add(a: Vec3, b: Vec3): Vec3 {
	return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

function subtract(a: Vec3, b: Vec3): Vec3 {
	return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function scale(value: Vec3, factor: number): Vec3 {
	return [value[0] * factor, value[1] * factor, value[2] * factor];
}

function magnitude(value: Vec3): number {
	return Math.hypot(value[0], value[1], value[2]);
}

function clamp(value: number, lower: number, upper: number): number {
	return Math.min(Math.max(value, lower), upper);
}

function lerp(start: number, end: number, t: number): number {
	return start + (end - start) * t;
}

function linspace(start: number, end: number, samples: number): number[] {
	if (samples <= 1) return [start];
	const values: number[] = [];
	for (let index = 0; index < samples; index += 1) {
		const ratio = samples === 1 ? 0 : index / (samples - 1);
		values.push(lerp(start, end, ratio));
	}
	return values;
}

export class CubicBezierCurve {
	p0: Vec3;
	p1: Vec3;
	p2: Vec3;
	p3: Vec3;

	constructor(p0: readonly number[] | Vec3, p1: readonly number[] | Vec3, p2: readonly number[] | Vec3, p3: readonly number[] | Vec3) {
		this.p0 = toVec3(p0);
		this.p1 = toVec3(p1);
		this.p2 = toVec3(p2);
		this.p3 = toVec3(p3);
	}

	evaluate(t: number): Vec3 {
		const clampedT = clamp(t, 0, 1);
		const mt = 1 - clampedT;

		const coeff0 = mt ** 3;
		const coeff1 = 3 * mt ** 2 * clampedT;
		const coeff2 = 3 * mt * clampedT ** 2;
		const coeff3 = clampedT ** 3;

		return [
			coeff0 * this.p0[0] + coeff1 * this.p1[0] + coeff2 * this.p2[0] + coeff3 * this.p3[0],
			coeff0 * this.p0[1] + coeff1 * this.p1[1] + coeff2 * this.p2[1] + coeff3 * this.p3[1],
			coeff0 * this.p0[2] + coeff1 * this.p1[2] + coeff2 * this.p2[2] + coeff3 * this.p3[2],
		];
	}

	derivative(t: number): Vec3 {
		const clampedT = clamp(t, 0, 1);
		const mt = 1 - clampedT;

		const term1 = scale(subtract(this.p1, this.p0), 3 * mt ** 2);
		const term2 = scale(subtract(this.p2, this.p1), 6 * mt * clampedT);
		const term3 = scale(subtract(this.p3, this.p2), 3 * clampedT ** 2);

		return add(add(term1, term2), term3);
	}

	arcLength(tStart = 0, tEnd = 1, samples = 100): number {
		const start = clamp(tStart, 0, 1);
		const end = clamp(tEnd, 0, 1);

		if (start >= end) return 0;

		const tValues = linspace(start, end, Math.max(2, Math.floor(samples)));
		let length = 0;

		for (let index = 0; index < tValues.length - 1; index += 1) {
			const pointA = this.evaluate(tValues[index]);
			const pointB = this.evaluate(tValues[index + 1]);
			length += magnitude(subtract(pointB, pointA));
		}

		return length;
	}

	totalArcLength(samples = 100): number {
		return this.arcLength(0, 1, samples);
	}
}

export class Spline3D {
	start: Vec3;
	end: Vec3;
	controlScaling: number;
	p1: Vec3;
	p2: Vec3;
	curve: CubicBezierCurve;

	constructor(start: readonly number[] | Vec3, end: readonly number[] | Vec3, controlScaling = 0.33) {
		this.start = toVec3(start);
		this.end = toVec3(end);
		this.controlScaling = Number(controlScaling);

		const direction = subtract(this.end, this.start);
		const distance = magnitude(direction);
		const directionNormalized = distance > 1e-9 ? scale(direction, 1 / distance) : [0, 0, 0];

		const offset = scale(direction, this.controlScaling);
		this.p1 = add(this.start, offset);
		this.p2 = subtract(this.end, offset);

		this.curve = new CubicBezierCurve(this.start, this.p1, this.p2, this.end);
		void directionNormalized;
	}

	evaluate(t: number): Vec3 {
		return this.curve.evaluate(t);
	}

	derivative(t: number): Vec3 {
		return this.curve.derivative(t);
	}

	sampleUniform(numPoints: number): Vec3[] {
		const pointCount = Math.max(2, Math.floor(numPoints));
		const tValues = linspace(0, 1, pointCount);
		return tValues.map((t) => this.evaluate(t));
	}

	sampleArcLength(numPoints: number, arcSamples = 50): Vec3[] {
		const pointCount = Math.max(2, Math.floor(numPoints));
		const totalLength = this.curve.totalArcLength(arcSamples);

		if (totalLength < 1e-9) {
			return Array.from({ length: pointCount }, () => [...this.start] as Vec3);
		}

		const targetLengths = linspace(0, totalLength, pointCount);
		return targetLengths.map((targetLength) => this.evaluate(this.findTForArcLength(targetLength, totalLength, arcSamples)));
	}

	sampleTimeBased(duration: number, dt = 0.01): Array<[Vec3, number]> {
		const step = dt > 0 ? dt : 0.01;
		const safeDuration = duration > 0 ? duration : 0;
		const stepCount = Math.max(2, Math.floor(safeDuration / step) + 1);
		const times = linspace(0, safeDuration, stepCount);

		return times.map((timeValue) => {
			const tParam = safeDuration > 0 ? clamp(timeValue / safeDuration, 0, 1) : 0;
			return [this.evaluate(tParam), timeValue];
		});
	}

	findTForArcLength(targetLength: number, totalLength: number, arcSamples = 50): number {
		if (totalLength < 1e-9) return 0;

		let tLow = 0;
		let tHigh = 1;

		for (let iteration = 0; iteration < 20; iteration += 1) {
			const tMid = (tLow + tHigh) / 2;
			const arcLength = this.curve.arcLength(0, tMid, arcSamples);

			if (arcLength < targetLength) {
				tLow = tMid;
			} else {
				tHigh = tMid;
			}
		}

		return (tLow + tHigh) / 2;
	}

	getTotalDistance(samples = 100): number {
		return this.curve.totalArcLength(samples);
	}
}
