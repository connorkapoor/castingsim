import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import './Viewer3D.css';

/**
 * Professional temperature color mapping
 * Maps temperature to color gradient: blue (cold) -> red (hot)
 */
function getTemperatureColor(temp, minTemp, maxTemp) {
  const t = Math.max(0, Math.min(1, (temp - minTemp) / (maxTemp - minTemp)));
  
  // Enhanced gradient: blue -> cyan -> green -> yellow -> orange -> red
  if (t < 0.2) {
    const s = t / 0.2;
    return new THREE.Color(0, s, 1);  // Blue to Cyan
  } else if (t < 0.4) {
    const s = (t - 0.2) / 0.2;
    return new THREE.Color(0, 1, 1 - s);  // Cyan to Green
  } else if (t < 0.6) {
    const s = (t - 0.4) / 0.2;
    return new THREE.Color(s, 1, 0);  // Green to Yellow
  } else if (t < 0.8) {
    const s = (t - 0.6) / 0.2;
    return new THREE.Color(1, 1 - 0.5 * s, 0);  // Yellow to Orange
  } else {
    const s = (t - 0.8) / 0.2;
    return new THREE.Color(1, 0.5 - 0.5 * s, 0);  // Orange to Red
  }
}

/**
 * Main casting mesh component with temperature visualization
 */
function CastingMesh({ mesh, temperatureData, material, isVoxelMesh = false }) {
  const meshRef = useRef();
  
  // For voxel mesh, we want wireframe + flat shading to show blocky structure
  const materialProps = isVoxelMesh ? {
    flatShading: true,
    wireframe: false,
    metalness: 0.1,
    roughness: 0.9
  } : {
    flatShading: false,
    metalness: 0.3,
    roughness: 0.6
  };
  
  // Debug logging
  useEffect(() => {
    console.log('🔍 CastingMesh received:', {
      hasMesh: !!mesh,
      nodes: mesh?.nodes?.length,
      elements: mesh?.elements?.length,
      surfaceTriangles: mesh?.surface_triangles?.length,
      hasTemperatureData: !!temperatureData,
      tempDataLength: temperatureData?.length,
      tempSample: temperatureData?.slice(0, 5)
    });
  }, [mesh, temperatureData]);
  
  // Create geometry from mesh
  const geometry = useMemo(() => {
    if (!mesh || !mesh.nodes) {
      console.warn('❌ No mesh data available');
      return null;
    }
    
    console.log('📐 Creating geometry...');
    const geo = new THREE.BufferGeometry();
    
    // Set vertices (convert from array of arrays to flat array)
    const vertices = new Float32Array(mesh.nodes.flat());
    geo.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    console.log(`  ✓ Vertices: ${vertices.length / 3} points`);
    
    // Set indices (surface triangles for rendering)
    const triangles = mesh.triangles || mesh.surface_triangles;
    if (triangles && triangles.length > 0) {
      const indices = new Uint32Array(triangles.flat());
      geo.setIndex(new THREE.BufferAttribute(indices, 1));
      console.log(`  ✓ Surface triangles: ${triangles.length} triangles`);
    } else if (mesh.elements) {
      // Fallback: use tetrahedra faces
      const faces = [];
      for (const tet of mesh.elements) {
        faces.push(tet[0], tet[1], tet[2]);
        faces.push(tet[0], tet[1], tet[3]);
        faces.push(tet[0], tet[2], tet[3]);
        faces.push(tet[1], tet[2], tet[3]);
      }
      geo.setIndex(faces);
      console.log(`  ✓ Tetrahedral faces: ${faces.length / 3} triangles`);
    }
    
    // Compute normals for smooth shading
    geo.computeVertexNormals();
    
    // Ensure normals are valid
    if (!geo.attributes.normal || geo.attributes.normal.count !== geo.attributes.position.count) {
      console.warn('⚠️ Normal computation issue, using flat shading');
      geo.deleteAttribute('normal');
    }
    
    // Center and scale geometry
    geo.computeBoundingBox();
    const center = new THREE.Vector3();
    geo.boundingBox.getCenter(center);
    geo.translate(-center.x, -center.y, -center.z);
    
    const size = new THREE.Vector3();
    geo.boundingBox.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = 50 / maxDim;
    geo.scale(scale, scale, scale);
    
    console.log(`  ✓ Geometry centered and scaled by ${scale.toFixed(3)}`);
    console.log(`  ✓ Bounding box size: ${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)} mm`);
    
    return geo;
  }, [mesh]);
  
  // Calculate vertex colors based on temperature
  const colors = useMemo(() => {
    if (!geometry) {
      console.warn('❌ No geometry for colors');
      return new Float32Array(0);
    }
    
    const vertexCount = geometry.attributes.position.count;
    
    if (!temperatureData || temperatureData.length === 0) {
      // Default: show hot orange/red colors to indicate no temperature data
      console.log(`🎨 Using default colors (no temperature data) for ${vertexCount} vertices`);
      const defaultColors = new Float32Array(vertexCount * 3);
      for (let i = 0; i < vertexCount; i++) {
        defaultColors[i * 3] = 1.0;     // R
        defaultColors[i * 3 + 1] = 0.5; // G
        defaultColors[i * 3 + 2] = 0.0; // B
      }
      return defaultColors;
    }
    
    const tempArray = temperatureData;
    
    // Check if temperature data matches vertex count
    if (tempArray.length !== vertexCount) {
      console.warn(`⚠️  Temperature data size mismatch: ${tempArray.length} temps vs ${vertexCount} vertices`);
      console.log(`🎨 Using default colors (size mismatch)`);
      const defaultColors = new Float32Array(vertexCount * 3);
      for (let i = 0; i < vertexCount; i++) {
        defaultColors[i * 3] = 0.7;     // R
        defaultColors[i * 3 + 1] = 0.7; // G
        defaultColors[i * 3 + 2] = 0.7; // B (gray for no data)
      }
      return defaultColors;
    }
    
    // Get temperature range
    const minTemp = Math.min(...tempArray);
    const maxTemp = Math.max(...tempArray);
    
    console.log(`🌡️  Temperature range: ${minTemp.toFixed(1)}°C - ${maxTemp.toFixed(1)}°C`);
    console.log(`🎨 Applying temperature colors to ${vertexCount} vertices`);
    
    const colors = new Float32Array(vertexCount * 3);
    
    for (let i = 0; i < vertexCount; i++) {
      const temp = tempArray[i] || minTemp;
      const color = getTemperatureColor(temp, minTemp, maxTemp);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    
    return colors;
  }, [geometry, temperatureData]);
  
  // Update colors on geometry
  useEffect(() => {
    if (geometry && colors.length > 0) {
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geometry.attributes.color.needsUpdate = true;
      console.log('✅ Colors applied to geometry');
    }
  }, [geometry, colors]);
  
  if (!geometry) {
    console.warn('⚠️  CastingMesh rendering null (no geometry)');
    return null;
  }
  
  console.log('✅ CastingMesh rendering mesh');
  
  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        vertexColors
        side={THREE.DoubleSide}
        {...materialProps}
      />
    </mesh>
  );
}

/**
 * Temperature legend component
 */
function TemperatureLegend({ temperatureData, material }) {
  if (!temperatureData || temperatureData.length === 0) {
    return (
      <div className="color-legend">
        <div className="legend-title">Temperature</div>
        <div className="legend-gradient"></div>
        <div className="legend-labels">
          <span>Cold</span>
          <span>Hot</span>
        </div>
        <div style={{ fontSize: '11px', color: '#999', marginTop: '5px' }}>
          No temperature data yet
        </div>
      </div>
    );
  }
  
  const minTemp = Math.min(...temperatureData);
  const maxTemp = Math.max(...temperatureData);
  
  return (
    <div className="color-legend">
      <div className="legend-title">Temperature Distribution</div>
      <div className="legend-gradient"></div>
      <div className="legend-labels">
        <span>{minTemp.toFixed(0)}°C</span>
        <span>{maxTemp.toFixed(0)}°C</span>
      </div>
      {material && (
        <div className="legend-info">
          <div>Melting: {material.melting_point}°C</div>
        </div>
      )}
    </div>
  );
}

/**
 * Main 3D viewer component
 */
function Viewer3D({ mesh, temperatureData, material, isVoxelMesh = false }) {
  // Debug logging
  useEffect(() => {
    console.log('🖥️  Viewer3D render:', {
      hasMesh: !!mesh,
      hasTemperatureData: !!temperatureData,
      hasMaterial: !!material
    });
  }, [mesh, temperatureData, material]);
  
  if (!mesh) {
    console.log('⚠️  Viewer3D: No mesh, showing placeholder');
    return (
      <div className="viewer3d">
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#666',
          fontSize: '18px',
          textAlign: 'center',
          padding: '20px',
          background: 'rgba(255,255,255,0.9)',
          borderRadius: '8px'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '20px' }}>📦</div>
          <div><strong>No geometry loaded</strong></div>
          <div style={{ fontSize: '14px', marginTop: '10px', color: '#999' }}>
            Upload an STL or STEP file to begin
          </div>
        </div>
      </div>
    );
  }
  
  console.log('✅ Viewer3D rendering Canvas with mesh');
  
  return (
    <div className="viewer3d">
      <Canvas camera={{ position: [80, 80, 80], fov: 50 }}>
        {/* Lighting */}
        <ambientLight intensity={0.6} />
        <directionalLight position={[10, 10, 5]} intensity={1.0} />
        <directionalLight position={[-10, -10, -5]} intensity={0.5} />
        <pointLight position={[0, 50, 0]} intensity={0.3} />
        
        {/* Casting mesh */}
        <CastingMesh 
          mesh={mesh}
          temperatureData={temperatureData}
          material={material}
          isVoxelMesh={isVoxelMesh}
        />
        
        {/* Controls */}
        <OrbitControls 
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
        />
      </Canvas>
      
      {/* Legend */}
      <TemperatureLegend temperatureData={temperatureData} material={material} />
      
      {/* Debug info overlay */}
      <div style={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        background: 'rgba(0,0,0,0.7)',
        color: 'white',
        padding: '8px 12px',
        borderRadius: '4px',
        fontSize: '11px',
        fontFamily: 'monospace'
      }}>
        <div>Nodes: {mesh?.nodes?.length || 0}</div>
        <div>Triangles: {mesh?.surface_triangles?.length || 0}</div>
        <div>Temp data: {temperatureData?.length || 0}</div>
      </div>
    </div>
  );
}

export default Viewer3D;
