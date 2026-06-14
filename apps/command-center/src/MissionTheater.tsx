import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { ApprovalDecision, DroneState, LivePolicyProposal, MissionPhase } from "./types";

interface MissionTheaterProps {
  phase: MissionPhase;
  proposal: LivePolicyProposal;
  approvalDecision: ApprovalDecision;
  heldOutcome: boolean;
}

const gridSize = 12;
const worldSize = 18;

export function MissionTheater({
  phase,
  proposal,
  approvalDecision,
  heldOutcome,
}: MissionTheaterProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof window.WebGLRenderingContext === "undefined") {
      return;
    }

    const theaterCanvas = canvas;
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      canvas: theaterCanvas,
      powerPreference: "high-performance",
    });
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 16 / 9, 0.1, 80);
    const clock = new THREE.Clock();
    const droneMeshes: THREE.Mesh[] = [];
    const floodMeshes: THREE.Mesh[] = [];
    const beaconMeshes: THREE.Mesh[] = [];
    const pulseMeshes: THREE.Mesh[] = [];
    const routeMeshes: THREE.Mesh[] = [];
    const relayLines: THREE.Line[] = [];
    const trailLines: THREE.Line[] = [];

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    camera.position.set(0, 13.5, phase.id === "mission-complete" ? 15.5 : 18);
    camera.lookAt(0, 0, 0);

    const root = new THREE.Group();
    root.rotation.x = -0.62;
    root.rotation.z = -0.06;
    scene.add(root);

    const ambient = new THREE.AmbientLight(0x9fffe8, 1.1);
    scene.add(ambient);

    const key = new THREE.DirectionalLight(0xc8ff64, 1.8);
    key.position.set(-4, 8, 8);
    scene.add(key);

    const deck = new THREE.Mesh(
      new THREE.PlaneGeometry(worldSize, worldSize, 36, 36),
      new THREE.MeshStandardMaterial({
        color: 0x071411,
        metalness: 0.18,
        roughness: 0.72,
        transparent: true,
        opacity: 0.92,
      }),
    );
    root.add(deck);

    const satelliteFrame = new THREE.Group();
    const frameMaterial = new THREE.LineBasicMaterial({
      color: 0x69e8db,
      transparent: true,
      opacity: 0.42,
    });
    const frameGeometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-worldSize * 0.43, -worldSize * 0.43, 0.24),
      new THREE.Vector3(worldSize * 0.43, -worldSize * 0.43, 0.24),
      new THREE.Vector3(worldSize * 0.43, worldSize * 0.43, 0.24),
      new THREE.Vector3(-worldSize * 0.43, worldSize * 0.43, 0.24),
      new THREE.Vector3(-worldSize * 0.43, -worldSize * 0.43, 0.24),
    ]);
    satelliteFrame.add(new THREE.Line(frameGeometry, frameMaterial));
    root.add(satelliteFrame);

    const grid = new THREE.GridHelper(worldSize, gridSize, 0x69e8db, 0x1c4746);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = 0.02;
    root.add(grid);

    const river = new THREE.Mesh(
      new THREE.PlaneGeometry(worldSize * 1.35, 2.1, 32, 1),
      new THREE.MeshBasicMaterial({
        color: 0x14798a,
        transparent: true,
        opacity: 0.28,
        side: THREE.DoubleSide,
      }),
    );
    river.position.set(0.2, -0.7, 0.05);
    river.rotation.z = -0.18;
    root.add(river);

    for (const cell of phase.mission.floodCells) {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1.18, 1.18, 0.08 + cell.probability * 0.7),
        new THREE.MeshStandardMaterial({
          color: 0x1bb5c1,
          emissive: 0x0b5c64,
          emissiveIntensity: 0.65,
          transparent: true,
          opacity: 0.28 + cell.probability * 0.38,
          roughness: 0.35,
        }),
      );
      mesh.position.copy(toWorld(cell.x, cell.y, cell.probability * 0.28));
      mesh.userData.delay = floodMeshes.length * 0.08;
      mesh.scale.setScalar(0.1);
      floodMeshes.push(mesh);
      root.add(mesh);

      const pulse = new THREE.Mesh(
        new THREE.RingGeometry(0.62, 0.78, 44),
        new THREE.MeshBasicMaterial({
          color: 0x69e8db,
          transparent: true,
          opacity: 0.12,
          side: THREE.DoubleSide,
        }),
      );
      pulse.position.copy(toWorld(cell.x, cell.y, 0.16));
      pulse.userData.delay = mesh.userData.delay;
      pulseMeshes.push(pulse);
      root.add(pulse);
    }

    for (const victim of phase.mission.victims) {
      const color = victim.status === "aided" ? 0xc8ff64 : victim.status === "confirmed" ? 0xffbd58 : 0xff6d5f;
      const beacon = new THREE.Mesh(
        new THREE.SphereGeometry(victim.status === "aided" ? 0.34 : 0.26, 24, 16),
        new THREE.MeshStandardMaterial({
          color,
          emissive: color,
          emissiveIntensity: victim.status === "aided" ? 1.6 : 1.1,
          transparent: true,
          opacity: 0.9,
        }),
      );
      beacon.position.copy(toWorld(victim.x, victim.y, 0.88));
      beaconMeshes.push(beacon);
      root.add(beacon);

      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.42, 0.55, 40),
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.65,
          side: THREE.DoubleSide,
        }),
      );
      ring.position.copy(toWorld(victim.x, victim.y, 0.11));
      beaconMeshes.push(ring);
      root.add(ring);
    }

    for (const drone of phase.mission.drones) {
      const mesh = new THREE.Mesh(
        new THREE.OctahedronGeometry(drone.role === "aid_drop" ? 0.34 : 0.26, 0),
        new THREE.MeshStandardMaterial({
          color: roleColor(drone.role),
          emissive: roleColor(drone.role),
          emissiveIntensity: 1.15,
          metalness: 0.45,
          roughness: 0.22,
        }),
      );
      mesh.position.copy(toWorld(drone.x, drone.y, drone.role === "relay" ? 1.55 : 1.25));
      mesh.userData.role = drone.role;
      droneMeshes.push(mesh);
      root.add(mesh);

      const trailStart = toWorld(
        drone.x + (drone.role === "return" ? -0.9 : -0.45),
        drone.y + (drone.role === "relay" ? 0.35 : 0.7),
        0.9,
      );
      const trail = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          trailStart,
          toWorld(drone.x, drone.y, drone.role === "relay" ? 1.46 : 1.16),
        ]),
        new THREE.LineBasicMaterial({
          color: roleColor(drone.role),
          transparent: true,
          opacity: drone.role === "hold" ? 0.14 : 0.34,
        }),
      );
      trailLines.push(trail);
      root.add(trail);
    }

    const aidDrone = phase.mission.drones.find((drone) => drone.id === "drone_4");
    const aidedVictim = phase.mission.victims.find((victim) => victim.id === "victim_alpha");
    if (
      aidDrone &&
      aidedVictim &&
      ["policy-handoff", "safety-review", "operator-approval", "aid-delivery", "mission-complete"].includes(phase.id)
    ) {
      const routeCurve = new THREE.CatmullRomCurve3([
        toWorld(aidDrone.x, aidDrone.y, 1.28),
        toWorld((aidDrone.x + aidedVictim.x) / 2 - 0.55, (aidDrone.y + aidedVictim.y) / 2, 2.25),
        toWorld(aidedVictim.x, aidedVictim.y, aidedVictim.status === "aided" ? 1.05 : 0.9),
      ]);
      const route = new THREE.Mesh(
        new THREE.TubeGeometry(routeCurve, 72, 0.035, 10, false),
        new THREE.MeshBasicMaterial({
          color: aidedVictim.status === "aided" ? 0xc8ff64 : 0xffbd58,
          transparent: true,
          opacity: 0.72,
        }),
      );
      routeMeshes.push(route);
      root.add(route);
    }

    for (const [from, to] of phase.mission.relayLinks) {
      const start = phase.mission.drones.find((drone) => drone.id === from);
      const end = phase.mission.drones.find((drone) => drone.id === to);
      if (!start || !end) {
        continue;
      }
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          toWorld(start.x, start.y, 1.35),
          toWorld(end.x, end.y, 1.35),
        ]),
        new THREE.LineBasicMaterial({
          color: 0xc8ff64,
          transparent: true,
          opacity: 0.58,
        }),
      );
      relayLines.push(line);
      root.add(line);
    }

    const scan = new THREE.Mesh(
      new THREE.PlaneGeometry(0.42, worldSize * 1.15),
      new THREE.MeshBasicMaterial({
        color: 0x69e8db,
        transparent: true,
        opacity: 0.28,
        side: THREE.DoubleSide,
      }),
    );
    scan.position.z = 0.35;
    root.add(scan);

    const approvalHalo = new THREE.Mesh(
      new THREE.TorusGeometry(4.2, 0.045, 12, 96),
      new THREE.MeshBasicMaterial({
        color: heldOutcome || approvalDecision === "held" ? 0xff6d5f : 0xc8ff64,
        transparent: true,
        opacity: phase.id === "mission-complete" || phase.id === "operator-approval" ? 0.8 : 0,
      }),
    );
    approvalHalo.position.z = 0.25;
    root.add(approvalHalo);

    function resize() {
      const bounds = theaterCanvas.getBoundingClientRect();
      const width = Math.max(bounds.width, 1);
      const height = Math.max(bounds.height, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    function animate() {
      const time = clock.getElapsedTime();
      resize();

      root.rotation.z = -0.06 + Math.sin(time * 0.2) * 0.015;
      satelliteFrame.rotation.z = Math.sin(time * 0.18) * 0.035;
      scan.position.x = ((time * 2.4) % (worldSize + 3)) - worldSize / 2 - 1.5;

      floodMeshes.forEach((mesh) => {
        const delay = Number(mesh.userData.delay ?? 0);
        const reveal = THREE.MathUtils.clamp((time - delay) * 2.3, 0, 1);
        mesh.scale.setScalar(THREE.MathUtils.lerp(mesh.scale.x, reveal, 0.12));
        mesh.rotation.z = Math.sin(time * 0.8 + delay) * 0.03;
      });

      pulseMeshes.forEach((mesh, index) => {
        const delay = Number(mesh.userData.delay ?? 0);
        const wave = 1 + Math.sin(time * 1.8 + index * 0.38 + delay) * 0.16;
        mesh.scale.setScalar(wave);
        const material = mesh.material as THREE.MeshBasicMaterial;
        material.opacity = 0.08 + Math.max(0, Math.sin(time * 1.4 + index)) * 0.16;
      });

      droneMeshes.forEach((mesh, index) => {
        const roleLift = mesh.userData.role === "relay" ? 0.18 : 0.1;
        mesh.position.z += Math.sin(time * 2.2 + index) * 0.004 + roleLift * 0.002;
        mesh.rotation.x += 0.018;
        mesh.rotation.y += 0.026;
      });

      beaconMeshes.forEach((mesh, index) => {
        const pulse = 1 + Math.sin(time * 2.5 + index) * 0.18;
        mesh.scale.setScalar(pulse);
        mesh.rotation.z += 0.018;
      });

      relayLines.forEach((line, index) => {
        const material = line.material as THREE.LineBasicMaterial;
        material.opacity = 0.34 + Math.sin(time * 3 + index) * 0.18 + 0.24;
      });

      trailLines.forEach((line, index) => {
        const material = line.material as THREE.LineBasicMaterial;
        material.opacity = 0.16 + Math.max(0, Math.sin(time * 3.2 + index * 0.7)) * 0.32;
      });

      routeMeshes.forEach((mesh) => {
        mesh.scale.setScalar(1 + Math.sin(time * 2.4) * 0.012);
        const material = mesh.material as THREE.MeshBasicMaterial;
        material.opacity = phase.id === "mission-complete" ? 0.9 : 0.54 + Math.sin(time * 2.1) * 0.18;
      });

      approvalHalo.rotation.z += 0.016;
      approvalHalo.scale.setScalar(1 + Math.sin(time * 1.8) * 0.04);

      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    }

    let animationFrame = window.requestAnimationFrame(animate);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      renderer.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
    };
  }, [approvalDecision, heldOutcome, phase, proposal]);

  return (
    <canvas
      ref={canvasRef}
      className="mission-theater"
      aria-hidden="true"
      data-phase={phase.id}
      data-proposal={proposal.proposal.action}
    />
  );
}

function toWorld(x: number, y: number, z: number): THREE.Vector3 {
  return new THREE.Vector3(
    (x / gridSize - 0.5) * worldSize + worldSize / gridSize / 2,
    (0.5 - y / gridSize) * worldSize - worldSize / gridSize / 2,
    z,
  );
}

function roleColor(role: DroneState["role"]): number {
  if (role === "aid_drop") {
    return 0xffbd58;
  }
  if (role === "relay") {
    return 0xc8ff64;
  }
  if (role === "hold" || role === "return") {
    return 0xff6d5f;
  }
  return 0x69e8db;
}
