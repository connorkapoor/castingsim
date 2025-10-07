import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, GizmoHelper, GizmoViewport } from '@react-three/drei';
import * as THREE from 'three';
import './Viewer3D.css';

function TemperatureColorMap(temperature, minTemp, maxTemp, meltingPoint) {
  const denom = Math.max(maxTemp - minTemp, 1e-6);
  let t = (temperature - minTemp) / denom;
  if (!Number.isFinite(t)) t = 0.5;
  t = Math.min(1, Math.max(0, t));
  
  // Color gradient: blue (cold) -> cyan -> green -> yellow -> orange -> red (hot)
  let color;
  
  if (t < 0.2) {
    // Blue to Cyan
    const localT = t / 0.2;
    color = new THREE.Color().setRGB(0, localT, 1);
  } else if (t < 0.4) {
    // Cyan to Green
    const localT = (t - 0.2) / 0.2;
    color = new THREE.Color().setRGB(0, 1, 1 - localT);
  } else if (t < 0.6) {
    // Green to Yellow
    const localT = (t - 0.4) / 0.2;
    color = new THREE.Color().setRGB(localT, 1, 0);
  } else if (t < 0.8) {
    // Yellow to Orange
    const localT = (t - 0.6) / 0.2;
    color = new THREE.Color().setRGB(1, 1 - 0.5 * localT, 0);
  } else {
    // Orange to Red
    const localT = (t - 0.8) / 0.2;
    color = new THREE.Color().setRGB(1, 0.5 - 0.5 * localT, 0);
  }
  
  return color;
}

function CastingMesh({ mesh, temperatureData, hotspotNodes, material }) {
  const meshRef = useRef();
  
  // No auto-rotation
  
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    
    const vertices = new Float32Array(mesh.nodes.flat());
    geo.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    
    // Use surface triangles for faces
    const indices = new Uint32Array(mesh.surface_triangles.flat());
    geo.setIndex(new THREE.BufferAttribute(indices, 1));
    
    geo.computeVertexNormals();
    // Center geometry at origin to ensure it's in view
    geo.computeBoundingBox();
    if (geo.boundingBox) {
      const center = new THREE.Vector3();
      geo.boundingBox.getCenter(center);
      geo.translate(-center.x, -center.y, -center.z);
    }
    
    return geo;
  }, [mesh]);
  
  const colors = useMemo(() => {
    if (!temperatureData || temperatureData.length === 0) return null;
    
    let minTemp = Math.min(...temperatureData);
    let maxTemp = Math.max(...temperatureData);
    const meltingPoint = material?.melting_point || 660;
    // Ensure a minimum visible range around melting point
    const pad = 150; // °C
    minTemp = Math.min(minTemp, meltingPoint - pad);
    maxTemp = Math.max(maxTemp, meltingPoint + pad);
    if (maxTemp - minTemp < 10) {
      minTemp -= 5;
      maxTemp += 5;
    }
    
    const colorArray = new Float32Array(mesh.nodes.length * 3);
    
    for (let i = 0; i < mesh.nodes.length; i++) {
      const temp = temperatureData[i];
      const color = TemperatureColorMap(temp, minTemp, maxTemp, meltingPoint);
      colorArray[i * 3] = color.r;
      colorArray[i * 3 + 1] = color.g;
      colorArray[i * 3 + 2] = color.b;
    }
    
    return colorArray;
  }, [temperatureData, mesh.nodes.length, material]);
  
  // Update colors on geometry reliably each frame
  useEffect(() => {
    if (!geometry || !colors) return;
    if (geometry.getAttribute('color')) {
      geometry.attributes.color.array = colors;
      geometry.attributes.color.needsUpdate = true;
    } else {
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    }
  }, [geometry, colors]);
  
  // Hotspot markers
  const hotspotMarkers = useMemo(() => {
    if (!hotspotNodes || hotspotNodes.length === 0) return null;
    
    return hotspotNodes.map(nodeIdx => {
      const pos = mesh.nodes[nodeIdx];
      return (
        <mesh key={nodeIdx} position={pos}>
          <sphereGeometry args={[1.5, 8, 8]} />
          <meshBasicMaterial color="#ff0000" transparent opacity={0.6} />
        </mesh>
      );
    });
  }, [hotspotNodes, mesh.nodes]);
  
  return (
    <group ref={meshRef}>
      <mesh geometry={geometry}>
        <meshStandardMaterial
          vertexColors
          toneMapped={false}
          metalness={0.2}
          roughness={0.6}
          side={THREE.DoubleSide}
        />
      </mesh>
      
      {/* Show clear part boundary with edge detection */}
      <mesh geometry={geometry}>
        <meshBasicMaterial 
          color="#000000" 
          wireframe={true}
          opacity={0.4}
          transparent
        />
      </mesh>
      {hotspotMarkers}
    </group>
  );
}

function DefectMarkers({ hotspotNodes, porosityNodes, nodes }) {
  // Show top 10 hotspots with labels
  const hotspots = (hotspotNodes || []).slice(0, 50).map((nodeIdx, i) => {
    const pos = nodes[nodeIdx];
    return (
      <group key={`hotspot-${nodeIdx}`} position={pos}>
        <mesh>
          <sphereGeometry args={[1.5, 12, 12]} />
          <meshBasicMaterial color="#ff0000" transparent opacity={0.8} />
        </mesh>
      </group>
    );
  });
  
  // Show top 10 porosity zones with labels
  const porosity = (porosityNodes || []).slice(0, 50).map((nodeIdx, i) => {
    const pos = nodes[nodeIdx];
    return (
      <group key={`porosity-${nodeIdx}`} position={pos}>
        <mesh>
          <sphereGeometry args={[1.5, 12, 12]} />
          <meshBasicMaterial color="#ffcc00" transparent opacity={0.8} />
        </mesh>
      </group>
    );
  });
  
  return (
    <>
      {hotspots}
      {porosity}
    </>
  );
}

function Viewer3D({ mesh, temperatureData, hotspotNodes, porosityNodes, material }) {
  if (!mesh) return null;
  
  return (
    <div className="viewer3d">
      <Canvas camera={{ position: [100, 100, 100], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <directionalLight position={[-10, -10, -5]} intensity={0.5} />
        
        <CastingMesh
          mesh={mesh}
          temperatureData={temperatureData}
          hotspotNodes={hotspotNodes}
          material={material}
        />
        
        <DefectMarkers 
          hotspotNodes={hotspotNodes}
          porosityNodes={porosityNodes}
          nodes={mesh.nodes}
        />
        
        <OrbitControls />
        
        <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
          <GizmoViewport labelColor="white" axisHeadScale={1} />
        </GizmoHelper>
        
      </Canvas>
      
      <div className="color-legend">
        <div className="legend-title">Temperature</div>
        <div className="legend-gradient"></div>
        <div className="legend-labels">
          <span>Cold</span>
          <span>Hot</span>
        </div>
      </div>
      
      <div className="defect-legend">
        <h4>Defect Indicators</h4>
        <div className="defect-item">
          <div className="defect-marker hotspot"></div>
          <span>Hotspots (Last to solidify)</span>
        </div>
        <div className="defect-item">
          <div className="defect-marker porosity"></div>
          <span>Porosity Risk (Niyama)</span>
        </div>
      </div>
    </div>
  );
}

export default Viewer3D;

