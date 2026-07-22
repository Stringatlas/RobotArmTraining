import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { ColladaLoader } from 'three/examples/jsm/loaders/ColladaLoader.js';
import URDFLoader, { type URDFRobot } from 'urdf-loader';

export interface RobotViewerOptions {
	urdfUrl: string;
	workingPath: string;
	backgroundColor?: number;
}

export class RobotViewer {
	private canvas: HTMLCanvasElement;
	private options: RobotViewerOptions;

	private scene: THREE.Scene;
	private camera: THREE.PerspectiveCamera;
	private renderer: THREE.WebGLRenderer;
	private controls: OrbitControls;
	private tcpMarker: THREE.Mesh;

	private robot: URDFRobot | null = null;
	private resizeObserver: ResizeObserver;
	private frameId: number | null = null;
	private disposed = false;

	constructor(canvas: HTMLCanvasElement, options: RobotViewerOptions) {
        this.canvas = canvas;
        this.options = options;

        THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(options.backgroundColor ?? 0x263238);

        const { clientWidth, clientHeight } = canvas;
        this.camera = new THREE.PerspectiveCamera(
            50,
            Math.max(clientWidth, 1) / Math.max(clientHeight, 1),
            0.01,
            50
        );
        this.camera.up.set(0, 0, 1); 
        this.camera.position.set(1.5, 1.5, 1.2); 

        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.setSize(clientWidth, clientHeight, false);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(0, 0, 0.3);
        this.controls.update();

        this.setupLights();
        this.setupGround();
		this.tcpMarker = this.createTcpMarker();
		this.scene.add(this.tcpMarker);

        this.resizeObserver = new ResizeObserver(() => this.handleResize());
        this.resizeObserver.observe(canvas);

        this.animate();
    }

    private setupLights() {
        const hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 1.2);
        this.scene.add(hemi);

        const dir = new THREE.DirectionalLight(0xffffff, 1.5);
        dir.position.set(2, 2, 4);
        dir.castShadow = true;
        dir.shadow.mapSize.set(1024, 1024);
        this.scene.add(dir);
    }

    private setupGround() {
        const grid = new THREE.GridHelper(4, 20, 0x666666, 0x444444);
        grid.rotation.x = Math.PI / 2;
        this.scene.add(grid);
    }

	/** Loads the URDF + meshes. Resolves once the robot is added to the scene. */
	async load(): Promise<URDFRobot> {
		const loader = new URDFLoader();
		loader.workingPath = this.options.workingPath;

		// Default loader only handles STL. Add Collada (.dae) support for
		// the gripper meshes, alongside STL for the arm links.
		// NOTE: the installed urdf-loader's *runtime* calls this with
		// (path, manager, material, onComplete) — 4 args — but its
		// published MeshLoadFunc type still only declares 3, so we cast
		// past that stale type rather than fight it.
		const loadMeshCb = (
			path: string,
			manager: THREE.LoadingManager,
			material: THREE.Material,
			onComplete: (obj: THREE.Object3D | null, err?: Error) => void
		) => {
			if (path.toLowerCase().endsWith('.dae')) {
				new ColladaLoader(manager).load(
					path,
					(result) => onComplete(result?.scene ?? null),
					undefined,
					(err) => onComplete(null, err as unknown as Error)
				);
			} else {
				new STLLoader(manager).load(
					path,
					(geometry) => {
						const mesh = new THREE.Mesh(
							geometry,
							material instanceof THREE.Material ? material : new THREE.MeshStandardMaterial()
						);
						onComplete(mesh);
					},
					undefined,
					(err) => onComplete(null, err as unknown as Error)
				);
			}
		};

		loader.loadMeshCb = loadMeshCb as any;
		return new Promise((resolve, reject) => {
			loader.load(
				this.options.urdfUrl,
				(robot) => {
					if (this.disposed) return;

					// robot.rotation.x = -Math.PI / 2; // URDF is Z-up, three.js is Y-up
					robot.traverse((c) => {
						c.castShadow = true;
						c.receiveShadow = true;
					});

					this.robot = robot;
					this.scene.add(robot);
					resolve(robot);
				},
				undefined,
				(err) => reject(err)
			);
		});
	}

	/** Set a single revolute/prismatic joint's angle (radians) or position (meters). */
	setJointAngle(jointName: string, value: number): boolean {
		if (!this.robot) return false;
		const joint = this.robot.joints[jointName];
		if (!joint) {
			console.warn(`[RobotViewer] no such joint: ${jointName}`);
			return false;
		}
		return joint.setJointValue(value);
	}

	/** Set multiple joints at once, e.g. { joint_1: 0.2, joint_2: -0.4 } */
	setJointAngles(values: Record<string, number>): void {
		if (!this.robot) return;
		this.robot.setJointValues(values);
	}

    setGripperValue(value: number): boolean {
        const jointName = 'gripper_r_joint1';
        const limits = this.getJointLimits(jointName);
        if (!limits) {
            console.warn(`[RobotViewer] no such joint or missing limits: ${jointName}`);
            return false;
        }

        const clamped = Math.min(100, Math.max(0, value));
        const t = clamped / 100; // normalize 0-100 to 0-1
        const angle = limits.lower + t * (limits.upper - limits.lower);

        return this.setJointAngle(jointName, angle);
    }

	/**
	 * Returns the world-space position of a named URDF frame after the current
	 * joint values have been applied.
	 */
	getFramePose(frameName: string): { position: THREE.Vector3, rotation: THREE.Euler } | undefined {
		if (!this.robot) return undefined;
		const frame = this.robot.getFrame(frameName);
		if (!frame) return undefined;

		this.robot.updateMatrixWorld(true);

		const position = new THREE.Vector3();
		frame.getWorldPosition(position);
        const q = new THREE.Quaternion();
        frame.getWorldQuaternion(q);
        const euler = new THREE.Euler().setFromQuaternion(q, 'ZYX');

		return { position: position, rotation: euler };
	}

	getToolheadCenterPose(): { position: THREE.Vector3, rotation: THREE.Euler } | undefined {
		return this.getFramePose('gripper_tip') ?? this.getFramePose('tool0');
	}

	private createTcpMarker(): THREE.Mesh {
		const geometry = new THREE.SphereGeometry(0.02, 24, 16);
		const material = new THREE.MeshBasicMaterial({ color: 0xff0000 });
		const marker = new THREE.Mesh(geometry, material);
		marker.visible = false;
		marker.renderOrder = 999;
		return marker;
	}

	private updateTcpMarker() {
		const pose = this.getToolheadCenterPose();
		if (!pose) {
			this.tcpMarker.visible = false;
			return;
		}

		this.tcpMarker.visible = true;
		this.tcpMarker.position.copy(pose.position);
	}

	addObject(object: THREE.Object3D): void {
		this.scene.add(object);
	}

	removeObject(object: THREE.Object3D): void {
		this.scene.remove(object);
	}

	getJointAngle(jointName: string): number | undefined {
		const joint = this.robot?.joints[jointName];
		if (!joint) return undefined;
		const v = joint.jointValue;
		return Array.isArray(v) ? v[0] : (v as unknown as number);
	}

	/** Names of all non-fixed joints, in document order. */
	getJointNames(): string[] {
		if (!this.robot) return [];
		return Object.values(this.robot.joints)
			.filter((j) => j.jointType !== 'fixed')
			.map((j) => j.name);
	}

	getJointLimits(jointName: string): { lower: number; upper: number } | undefined {
		const joint = this.robot?.joints[jointName];
		if (!joint) return undefined;
		return { lower: joint.limit.lower as number, upper: joint.limit.upper as number };
	}

	private handleResize() {
		const { clientWidth, clientHeight } = this.canvas;
		if (clientWidth === 0 || clientHeight === 0) return;
		this.camera.aspect = clientWidth / clientHeight;
		this.camera.updateProjectionMatrix();
		this.renderer.setSize(clientWidth, clientHeight, false);
	}

	private animate = () => {
		if (this.disposed) return;
		this.frameId = requestAnimationFrame(this.animate);
		this.controls.update();
		this.updateTcpMarker();
		this.renderer.render(this.scene, this.camera);
	};

	/** Tear down all GPU resources, observers, and the render loop. */
	dispose() {
		this.disposed = true;
		if (this.frameId !== null) cancelAnimationFrame(this.frameId);
		this.resizeObserver.disconnect();
		this.controls.dispose();

		this.scene.traverse((obj) => {
			const mesh = obj as THREE.Mesh;
			if (mesh.geometry) mesh.geometry.dispose();
			const material = mesh.material;
			if (Array.isArray(material)) material.forEach((m) => m.dispose());
			else if (material) (material as THREE.Material).dispose();
		});

		this.renderer.dispose();
	}
}