import math
import json
import argparse
import tempfile
import webbrowser
import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Circle # For potential 2D projection if needed
from matplotlib.collections import PatchCollection # For potential 2D projection

# --- Core PMT Placement Logic (Unchanged from previous version) ---
def generate_pmt_info(
    box_full_dims_mm,
    pmt_physical_diameter_mm,
    distance_edge_to_wall_mm,
    desired_photo_coverage,
    pmt_active_diameter_mm=None,
    min_pmt_edge_to_face_edge_gap_mm=0.0
    ):
    """
    Generates PMT positions and orientations for a box detector.
    """
    if pmt_active_diameter_mm is None:
        pmt_active_diameter_mm = 460.0 # Default active diameter for ~20-inch PMT

    box_half_dims_mm = [d / 2.0 for d in box_full_dims_mm]
    pmt_physical_radius_mm = pmt_physical_diameter_mm / 2.0
    pmt_active_radius_mm = pmt_active_diameter_mm / 2.0
    pmt_active_area_single_mm2 = math.pi * (pmt_active_radius_mm ** 2)
    pmt_center_offset_from_wall_mm = pmt_physical_radius_mm + distance_edge_to_wall_mm

    xs, ys, zs = [], [], []
    dir_xs, dir_ys, dir_zs = [], [], []
    types = []

    wall_definitions = [
        {'id': '+X Wall', 'face_dims_indices': [1, 2], 'fixed_coord_idx': 0, 'fixed_coord_sign': 1,  'orientation_vec': [-1, 0, 0]},
        {'id': '-X Wall', 'face_dims_indices': [1, 2], 'fixed_coord_idx': 0, 'fixed_coord_sign': -1, 'orientation_vec': [1, 0, 0]},
        {'id': '+Y Wall', 'face_dims_indices': [0, 2], 'fixed_coord_idx': 1, 'fixed_coord_sign': 1,  'orientation_vec': [0, -1, 0]},
        {'id': '-Y Wall', 'face_dims_indices': [0, 2], 'fixed_coord_idx': 1, 'fixed_coord_sign': -1, 'orientation_vec': [0, 1, 0]},
        {'id': '+Z Wall', 'face_dims_indices': [0, 1], 'fixed_coord_idx': 2, 'fixed_coord_sign': 1,  'orientation_vec': [0, 0, -1]},
        {'id': '-Z Wall', 'face_dims_indices': [0, 1], 'fixed_coord_idx': 2, 'fixed_coord_sign': -1, 'orientation_vec': [0, 0, 1]},
    ]

    total_wall_surface_area_mm2 = 0
    face_info_list = []

    for i, wall_def in enumerate(wall_definitions):
        face_dim1_full = box_full_dims_mm[wall_def['face_dims_indices'][0]]
        face_dim2_full = box_full_dims_mm[wall_def['face_dims_indices'][1]]
        current_face_area = face_dim1_full * face_dim2_full
        total_wall_surface_area_mm2 += current_face_area

        eff_place_len_dim1 = face_dim1_full - 2 * (pmt_physical_radius_mm + min_pmt_edge_to_face_edge_gap_mm)
        eff_place_len_dim2 = face_dim2_full - 2 * (pmt_physical_radius_mm + min_pmt_edge_to_face_edge_gap_mm)
        
        n1_max_fit = 0
        if eff_place_len_dim1 < 0: n1_max_fit = 0
        elif eff_place_len_dim1 < pmt_physical_diameter_mm: n1_max_fit = 1
        else: n1_max_fit = math.floor(eff_place_len_dim1 / pmt_physical_diameter_mm) + 1

        n2_max_fit = 0
        if eff_place_len_dim2 < 0: n2_max_fit = 0
        elif eff_place_len_dim2 < pmt_physical_diameter_mm: n2_max_fit = 1
        else: n2_max_fit = math.floor(eff_place_len_dim2 / pmt_physical_diameter_mm) + 1
        
        max_pmts_on_face = n1_max_fit * n2_max_fit
        if eff_place_len_dim1 < 0 or eff_place_len_dim2 < 0 : max_pmts_on_face = 0


        pattern_area_dim1 = face_dim1_full - 2 * min_pmt_edge_to_face_edge_gap_mm
        pattern_area_dim2 = face_dim2_full - 2 * min_pmt_edge_to_face_edge_gap_mm

        face_info_list.append({
            'id': wall_def['id'], 'wall_def_idx': i, 'face_area_mm2': current_face_area,
            'pattern_area_dim1': pattern_area_dim1, 'pattern_area_dim2': pattern_area_dim2,
            'n1_max_theoretical': n1_max_fit, 'n2_max_theoretical': n2_max_fit,
            'max_fit_pmts': max_pmts_on_face
        })

    N_target_pmts_for_coverage = 0
    if total_wall_surface_area_mm2 > 0 and pmt_active_area_single_mm2 > 0:
        N_target_pmts_for_coverage = math.ceil(
            desired_photo_coverage * total_wall_surface_area_mm2 / pmt_active_area_single_mm2
        )

    N_max_physically_possible_pmts = sum(fi['max_fit_pmts'] for fi in face_info_list)
    N_actual_total_to_place = 0

    if N_max_physically_possible_pmts == 0:
        print("WARNING: No PMTs can be placed with the given geometric constraints.")
    elif N_target_pmts_for_coverage > N_max_physically_possible_pmts:
        print(f"WARNING: Desired photocoverage {desired_photo_coverage*100:.2f}% requires {N_target_pmts_for_coverage} PMTs.")
        print(f"         Only {N_max_physically_possible_pmts} PMTs can physically fit. Placing max possible.")
        N_actual_total_to_place = N_max_physically_possible_pmts
    else:
        N_actual_total_to_place = N_target_pmts_for_coverage

    num_pmts_allocated_to_face = [0] * len(face_info_list)
    if N_max_physically_possible_pmts > 0 and N_actual_total_to_place > 0:
        temp_allocations = []
        for i_face, fi_face in enumerate(face_info_list):
            ideal_share_float = (N_actual_total_to_place * (fi_face['max_fit_pmts'] / N_max_physically_possible_pmts if N_max_physically_possible_pmts > 0 else 0))
            capped_ideal = min(ideal_share_float, fi_face['max_fit_pmts'])
            num_pmts_allocated_to_face[i_face] = math.floor(capped_ideal)
            temp_allocations.append({
                'face_idx': i_face,
                'fractional_part': capped_ideal - math.floor(capped_ideal),
                'max_fit': fi_face['max_fit_pmts']
            })
        
        current_sum_allocated = sum(num_pmts_allocated_to_face)
        remainder_pmts = N_actual_total_to_place - current_sum_allocated
        temp_allocations.sort(key=lambda x: x['fractional_part'], reverse=True)

        for alloc_info in temp_allocations:
            if remainder_pmts <= 0: break
            face_idx = alloc_info['face_idx']
            if num_pmts_allocated_to_face[face_idx] < alloc_info['max_fit']:
                num_pmts_allocated_to_face[face_idx] += 1
                remainder_pmts -= 1
        
        if remainder_pmts > 0: # If still remainder, distribute to faces with capacity
            for face_idx_ordered in sorted(range(len(face_info_list)), key=lambda k: face_info_list[k]['max_fit_pmts'], reverse=True):
                 if remainder_pmts <= 0: break
                 if num_pmts_allocated_to_face[face_idx_ordered] < face_info_list[face_idx_ordered]['max_fit_pmts']:
                     num_pmts_allocated_to_face[face_idx_ordered] += 1
                     remainder_pmts -=1


    total_pmts_placed_count = 0
    for i_face_main, fi_face_main in enumerate(face_info_list):
        num_to_place_on_this_face = num_pmts_allocated_to_face[i_face_main]
        if num_to_place_on_this_face == 0: continue

        wall_def = wall_definitions[fi_face_main['wall_def_idx']]
        pattern_dim1 = fi_face_main['pattern_area_dim1']
        pattern_dim2 = fi_face_main['pattern_area_dim2']

        if pattern_dim1 < 0 or pattern_dim2 < 0 : continue

        n_along_d1, n_along_d2 = 1, 1 # Default for single PMT
        if num_to_place_on_this_face > 0 :
            if num_to_place_on_this_face == fi_face_main['max_fit_pmts'] and fi_face_main['n1_max_theoretical'] > 0 and fi_face_main['n2_max_theoretical'] > 0 :
                n_along_d1 = fi_face_main['n1_max_theoretical']
                n_along_d2 = fi_face_main['n2_max_theoretical']
            elif pattern_dim1 <= 0 or pattern_dim2 <= 0: # Check if pattern area is non-zero for both dimensions
                 if pattern_dim1 <= 0 and pattern_dim2 > 0 : n_along_d1 = 1; n_along_d2 = num_to_place_on_this_face
                 elif pattern_dim2 <= 0 and pattern_dim1 > 0 : n_along_d1 = num_to_place_on_this_face; n_along_d2 = 1
                 else: continue # Cannot place if both pattern dimensions are zero or negative
            else: # General case for grid placement
                aspect_ratio_pattern_area = pattern_dim1 / pattern_dim2
                n_along_d1 = math.ceil(math.sqrt(num_to_place_on_this_face * aspect_ratio_pattern_area))
                if n_along_d1 == 0: n_along_d1 = 1 # Ensure at least 1
                n_along_d2 = math.ceil(num_to_place_on_this_face / n_along_d1)
                if n_along_d2 == 0: n_along_d2 = 1 # Ensure at least 1

                # Refine grid to be as compact as possible for num_to_place_on_this_face
                while n_along_d1 > 0 and n_along_d2 > 0:
                    if n_along_d1 * (n_along_d2 - 1) >= num_to_place_on_this_face and n_along_d2 > 1:
                        n_along_d2 -= 1
                    elif (n_along_d1 - 1) * n_along_d2 >= num_to_place_on_this_face and n_along_d1 > 1:
                        n_along_d1 -= 1
                    else:
                        break
                if n_along_d1 == 0: n_along_d1 = 1
                if n_along_d2 == 0: n_along_d2 = 1
        else: continue # No PMTs to place on this face

        cell_spacing_d1 = pattern_dim1 / n_along_d1 if n_along_d1 > 0 else pattern_dim1
        cell_spacing_d2 = pattern_dim2 / n_along_d2 if n_along_d2 > 0 else pattern_dim2
        
        if n_along_d1 > 0 and cell_spacing_d1 < pmt_physical_diameter_mm - 1e-3 and num_to_place_on_this_face > 1 and n_along_d1 * n_along_d2 > num_to_place_on_this_face : # check if actual cells are more than needed
             print(f"  INFO on {wall_def['id']}: cell_spacing_d1 ({cell_spacing_d1:.2f}mm) might be tight for PMT diameter ({pmt_physical_diameter_mm:.2f}mm) with {n_along_d1} PMTs. Consider constraints.")
        if n_along_d2 > 0 and cell_spacing_d2 < pmt_physical_diameter_mm - 1e-3 and num_to_place_on_this_face > 1 and n_along_d1 * n_along_d2 > num_to_place_on_this_face :
             print(f"  INFO on {wall_def['id']}: cell_spacing_d2 ({cell_spacing_d2:.2f}mm) might be tight for PMT diameter ({pmt_physical_diameter_mm:.2f}mm) with {n_along_d2} PMTs. Consider constraints.")

        pmt_count_on_this_face = 0
        for r_idx in range(int(n_along_d1)):
            if pmt_count_on_this_face >= num_to_place_on_this_face: break
            for c_idx in range(int(n_along_d2)):
                if pmt_count_on_this_face >= num_to_place_on_this_face: break
                
                u = (-pattern_dim1 / 2.0) + (cell_spacing_d1 / 2.0) + (r_idx * cell_spacing_d1) if n_along_d1 > 0 else 0
                v = (-pattern_dim2 / 2.0) + (cell_spacing_d2 / 2.0) + (c_idx * cell_spacing_d2) if n_along_d2 > 0 else 0

                pos = [0.0, 0.0, 0.0]
                fixed_coord_center_val = (wall_def['fixed_coord_sign'] * box_half_dims_mm[wall_def['fixed_coord_idx']]) - \
                                         (wall_def['fixed_coord_sign'] * pmt_center_offset_from_wall_mm)
                pos[wall_def['fixed_coord_idx']] = fixed_coord_center_val
                
                if wall_def['fixed_coord_idx'] == 0: pos[1], pos[2] = u, v
                elif wall_def['fixed_coord_idx'] == 1: pos[0], pos[2] = u, v
                elif wall_def['fixed_coord_idx'] == 2: pos[0], pos[1] = u, v
                
                xs.append(pos[0])
                ys.append(pos[1])
                zs.append(pos[2])
                dir_xs.append(float(wall_def['orientation_vec'][0]))
                dir_ys.append(float(wall_def['orientation_vec'][1]))
                dir_zs.append(float(wall_def['orientation_vec'][2]))
                types.append(1)
                pmt_count_on_this_face += 1
        total_pmts_placed_count += pmt_count_on_this_face

    pmtinfo_dict = {
        "name": "PMTINFO", "valid_begin": [0, 0], "valid_end": [0, 0],
        "x": xs, "y": ys, "z": zs,
        "dir_x": dir_xs, "dir_y": dir_ys, "dir_z": dir_zs, "type": types
    }
    achieved_coverage = 0.0
    if total_wall_surface_area_mm2 > 0 and pmt_active_area_single_mm2 > 0 and total_pmts_placed_count > 0:
        achieved_coverage = (total_pmts_placed_count * pmt_active_area_single_mm2) / total_wall_surface_area_mm2

    summary = {
        "total_pmts_placed": total_pmts_placed_count,
        "desired_photocoverage_input": desired_photo_coverage,
        "achieved_photocoverage_calculated": achieved_coverage,
        "pmt_active_diameter_used_mm": pmt_active_diameter_mm,
        "pmt_physical_diameter_mm": pmt_physical_diameter_mm,
        "distance_edge_to_wall_mm": distance_edge_to_wall_mm,
        "min_pmt_edge_to_face_edge_gap_mm": min_pmt_edge_to_face_edge_gap_mm,
        "N_target_for_coverage_calc": N_target_pmts_for_coverage,
        "N_max_physically_possible_calc": N_max_physically_possible_pmts,
        "num_on_each_face" : [{face_info_list[i]['id']: num_pmts_allocated_to_face[i]} for i in range(len(face_info_list))]
    }
    return pmtinfo_dict, summary

# --- HTML Generation for Visualization (Unchanged) ---
def generate_visualization_html(detector_dims, pmt_data_for_js, pmt_physical_diameter_mm):
    pmt_radius_mm = pmt_physical_diameter_mm / 2.0
    pmt_render_length_mm = pmt_physical_diameter_mm * 0.8
    pmt_data_json_string = json.dumps(pmt_data_for_js, indent=None)
    html_template = f"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3D Detector Visualization</title><style>body {{ margin: 0; font-family: Arial, sans-serif; background-color: #f0f0f0; color: #333; overflow: hidden; }}
#container {{ width: 100vw; height: 100vh; display: block; }} #infoBox {{ position: absolute; top: 10px; left: 10px; padding: 10px;
background-color: rgba(255, 255, 255, 0.9); border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-size: 12px; max-width: 300px; }}
canvas {{ display: block; }}</style></head><body><div id="infoBox"><p><strong>3D Detector Visualization</strong></p>
<p>Detector (Lx,Ly,Lz): {detector_dims[0]:.0f}, {detector_dims[1]:.0f}, {detector_dims[2]:.0f} mm</p>
<p>PMTs: {len(pmt_data_for_js)} placed ({pmt_physical_diameter_mm:.1f} mm diameter)</p><p>Controls: Orbit (LMB), Zoom (Scroll), Pan (RMB)</p></div>
<div id="container"></div><script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script><script>
const DETECTOR_SIZE = [{detector_dims[0]}, {detector_dims[1]}, {detector_dims[2]}]; const PMT_RADIUS_MM = {pmt_radius_mm};
const PMT_RENDER_LENGTH_MM = {pmt_render_length_mm}; const pmtData = JSON.parse('{pmt_data_json_string}');
let scene, camera, renderer, controls; function init() {{ scene = new THREE.Scene(); scene.background = new THREE.Color(0xcccccc);
const aspect = window.innerWidth / window.innerHeight; camera = new THREE.PerspectiveCamera(50, aspect, 10, 200000);
const maxDim = Math.max(...DETECTOR_SIZE); camera.position.set(maxDim * 0.8, maxDim * 0.6, maxDim * 1.3); camera.lookAt(0, 0, 0);
renderer = new THREE.WebGLRenderer({{ antialias: true }}); renderer.setSize(window.innerWidth, window.innerHeight);
document.getElementById('container').appendChild(renderer.domElement); controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.05; const ambientLight = new THREE.AmbientLight(0xffffff, 0.7); scene.add(ambientLight);
const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.6); dirLight1.position.set(1, 1.5, 1).normalize(); scene.add(dirLight1);
const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.3); dirLight2.position.set(-1, -0.5, -1).normalize(); scene.add(dirLight2);
const axesHelper = new THREE.AxesHelper(Math.max(...DETECTOR_SIZE) / 3); scene.add(axesHelper); createDetectorBox(); createPMTs();
window.addEventListener('resize', onWindowResize, false); animate(); }} function createDetectorBox() {{ const boxGeom = new THREE.BoxGeometry(DETECTOR_SIZE[0], DETECTOR_SIZE[1], DETECTOR_SIZE[2]);
const boxMat = new THREE.MeshStandardMaterial({{ color: 0x5577aa, transparent: true, opacity: 0.2, side: THREE.DoubleSide }});
const boxMesh = new THREE.Mesh(boxGeom, boxMat); scene.add(boxMesh); const edgesGeom = new THREE.EdgesGeometry(boxGeom);
const edgesMat = new THREE.LineBasicMaterial({{ color: 0x223355, linewidth: 1 }}); boxMesh.add(new THREE.LineSegments(edgesGeom, edgesMat)); }}
function createPMTs() {{ const pmtGeom = new THREE.CylinderGeometry(PMT_RADIUS_MM, PMT_RADIUS_MM, PMT_RENDER_LENGTH_MM, 24);
const pmtMat = new THREE.MeshStandardMaterial({{ color: 0xff8c00, emissive: 0x221100 }}); pmtData.forEach(data => {{
const pmtMesh = new THREE.Mesh(pmtGeom, pmtMat); pmtMesh.position.set(data.x, data.y, data.z);
const direction = new THREE.Vector3(data.dir_x, data.dir_y, data.dir_z).normalize(); const defaultAxis = new THREE.Vector3(0, 1, 0);
const quaternion = new THREE.Quaternion().setFromUnitVectors(defaultAxis, direction); pmtMesh.quaternion.multiply(quaternion); scene.add(pmtMesh); }}); }}
function onWindowResize() {{ camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth, window.innerHeight); }}
function animate() {{ requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }} init(); </script></body></html>"""
    return html_template

# --- Matplotlib Visualization (Unchanged) ---
def plot_matplotlib_visualization(detector_dims, pmt_data_list, pmt_physical_diameter_mm):
    """
    Generates a 3D visualization using Matplotlib.
    Args:
        detector_dims (list): [Lx, Ly, Lz] of the detector box.
        pmt_data_list (list): List of dicts, each {x, y, z, dir_x, dir_y, dir_z}.
        pmt_physical_diameter_mm (float): Physical diameter of PMTs for rendering.
    """
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    hx, hy, hz = detector_dims[0] / 2, detector_dims[1] / 2, detector_dims[2] / 2

    # 1. Plot Detector Box (as semi-transparent faces)
    vertices = np.array([
        [-hx, -hy, -hz], [ hx, -hy, -hz], [ hx,  hy, -hz], [-hx,  hy, -hz],
        [-hx, -hy,  hz], [ hx, -hy,  hz], [ hx,  hy,  hz], [-hx,  hy,  hz]
    ])
    faces = [
        [vertices[0], vertices[1], vertices[2], vertices[3]], 
        [vertices[4], vertices[5], vertices[6], vertices[7]], 
        [vertices[0], vertices[1], vertices[5], vertices[4]], 
        [vertices[2], vertices[3], vertices[7], vertices[6]], 
        [vertices[1], vertices[2], vertices[6], vertices[5]], 
        [vertices[4], vertices[7], vertices[3], vertices[0]]
    ]
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    ax.add_collection3d(Poly3DCollection(faces, facecolors='cyan', linewidths=1, edgecolors='darkblue', alpha=.10))

    # 2. Plot PMTs (as cylinders)
    pmt_radius = pmt_physical_diameter_mm / 2.0
    pmt_length = pmt_physical_diameter_mm * 0.8 

    for pmt_data in pmt_data_list:
        center = np.array([pmt_data['x'], pmt_data['y'], pmt_data['z']])
        direction = np.array([pmt_data['dir_x'], pmt_data['dir_y'], pmt_data['dir_z']])
        direction = direction / np.linalg.norm(direction) 

        u = np.linspace(0, 2 * np.pi, 20)
        h_cyl = np.linspace(-pmt_length / 2, pmt_length / 2, 2) 
        x_cyl = pmt_radius * np.cos(u)
        y_cyl = pmt_radius * np.sin(u)
        
        X_canonical = np.outer(x_cyl, np.ones_like(h_cyl))
        Y_canonical = np.outer(y_cyl, np.ones_like(h_cyl))
        Z_canonical = np.outer(np.ones_like(u), h_cyl)

        z_axis = np.array([0, 0, 1])
        axis = np.cross(z_axis, direction)
        angle = np.arccos(np.dot(z_axis, direction))

        if np.linalg.norm(axis) < 1e-6: 
            if np.dot(z_axis, direction) > 0: 
                rot_matrix = np.identity(3)
            else: 
                if direction[2] < -0.999: 
                    rot_matrix = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
                else: 
                    rot_matrix = np.identity(3)
        else:
            axis = axis / np.linalg.norm(axis)
            K = np.array([[0, -axis[2], axis[1]],
                          [axis[2], 0, -axis[0]],
                          [-axis[1], axis[0], 0]])
            rot_matrix = np.identity(3) + np.sin(angle) * K + (1 - np.cos(angle)) * np.dot(K, K)

        X_rot, Y_rot, Z_rot = np.zeros_like(X_canonical), np.zeros_like(X_canonical), np.zeros_like(X_canonical)
        for i in range(X_canonical.shape[0]):
            for j in range(X_canonical.shape[1]):
                point = np.array([X_canonical[i,j], Y_canonical[i,j], Z_canonical[i,j]])
                rotated_point = np.dot(rot_matrix, point)
                translated_point = rotated_point + center
                X_rot[i,j], Y_rot[i,j], Z_rot[i,j] = translated_point
        
        ax.plot_surface(X_rot, Y_rot, Z_rot, color='orange', alpha=0.7, rstride=1, cstride=1)

        cap_center = center + direction * (pmt_length / 2.0)
        circle_x = pmt_radius * np.cos(u)
        circle_y = pmt_radius * np.sin(u)
        circle_z = np.zeros_like(u)
        
        cap_points = np.vstack([circle_x, circle_y, circle_z])
        rotated_cap_points = np.dot(rot_matrix, cap_points)
        translated_cap_points = rotated_cap_points + cap_center[:, np.newaxis]
        
        ax.plot(translated_cap_points[0,:], translated_cap_points[1,:], translated_cap_points[2,:], color='darkgoldenrod', linewidth=1.5)

    max_range = np.array([detector_dims[0], detector_dims[1], detector_dims[2]]).max() / 1.8
    mid_x, mid_y, mid_z = 0, 0, 0 
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')
    ax.set_title(f'Detector Visualization ({len(pmt_data_list)} PMTs)')
    plt.show()


# --- Main Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate PMT positions for a box detector and visualize.")
    parser.add_argument("--detector_size", type=str, default="10500,35100,9600",
                        help="Lx,Ly,Lz of the detector box in mm (comma-separated, no spaces).")
    parser.add_argument("--pmt_physical_diameter", type=float, default=20 * 25.4,
                        help="Physical diameter of PMTs in mm (default: 20 inches).")
    parser.add_argument("--distance_edge_to_wall", type=float, default=50.0,
                        help="Distance from PMT edge to the wall it's mounted on (mm).")
    parser.add_argument("--desired_photo_coverage", type=float, default=0.20,
                        help="Desired photocathode coverage (0.0 to 1.0).")
    parser.add_argument("--pmt_active_diameter", type=float, default=460.0,
                        help="Active photocathode diameter in mm (default: 460mm for typical 20-inch).")
    parser.add_argument("--min_pmt_edge_to_face_edge_gap", type=float, default=10.0,
                        help="Minimum gap from PMT edge to the edge of the detector face (mm).")
    parser.add_argument("--output_pmtinfo_file", type=str, default=None,
                        help="Optional: Path to save the PMTINFO JSON data (e.g., pmtinfo.json).")
    parser.add_argument("--visualization_type", type=str, default="html", choices=["html", "matplotlib", "none"],
                        help="Type of visualization to use: 'html', 'matplotlib', or 'none'. Default is 'html'.")

    args = parser.parse_args()

    try:
        detector_dims = [float(d) for d in args.detector_size.split(',')]
        if len(detector_dims) != 3:
            raise ValueError("Detector size must have 3 dimensions (Lx,Ly,Lz).")
    except ValueError as e:
        print(f"Error parsing detector_size: {e}")
        print("Please provide detector_size as Lx,Ly,Lz (e.g., --detector_size 1000,2000,3000)")
        exit(1)

    print("--- Running PMT Placement ---")
    print(f"Detector Dimensions (Lx,Ly,Lz): {detector_dims} mm")
    print(f"PMT Physical Diameter: {args.pmt_physical_diameter:.2f} mm")
    print(f"PMT Active Diameter (for coverage): {args.pmt_active_diameter:.2f} mm")
    print(f"Distance PMT Edge to Wall: {args.distance_edge_to_wall:.2f} mm")
    print(f"Desired Photocoverage: {args.desired_photo_coverage*100:.2f}%")
    print(f"Min PMT Edge to Face Edge Gap: {args.min_pmt_edge_to_face_edge_gap:.2f} mm")
    print("-" * 30)

    pmtinfo_data, summary = generate_pmt_info(
        box_full_dims_mm=detector_dims,
        pmt_physical_diameter_mm=args.pmt_physical_diameter,
        distance_edge_to_wall_mm=args.distance_edge_to_wall,
        desired_photo_coverage=args.desired_photo_coverage,
        pmt_active_diameter_mm=args.pmt_active_diameter,
        min_pmt_edge_to_face_edge_gap_mm=args.min_pmt_edge_to_face_edge_gap
    )

    print("\n--- Placement Summary ---")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        elif isinstance(value, list) and key == "num_on_each_face":
            print(f"  {key}:")
            for item in value:
                for wall_id, count in item.items():
                    print(f"    {wall_id}: {count}")
        else:
            print(f"  {key}: {value}")

    if args.output_pmtinfo_file:
        try:
            with open(args.output_pmtinfo_file, 'w') as f:
                f.write("{\n") # Start the JSON object
                num_items = len(pmtinfo_data)
                for i, (key, value) in enumerate(pmtinfo_data.items()):
                    # Write key with 2-space indent
                    f.write(f'  "{key}": ') 
                    
                    # For specific long lists, write them compactly
                    if isinstance(value, list) and key in ['x', 'y', 'z', 'dir_x', 'dir_y', 'dir_z', 'type']:
                        f.write(json.dumps(value, separators=(',', ':')))
                    else:
                        # For other values (strings, short lists like valid_begin), use standard dumps
                        f.write(json.dumps(value))
                    
                    # Add comma and newline if not the last item
                    if i < num_items - 1:
                        f.write(",\n")
                    else:
                        f.write("\n") # Just a newline for the last item
                f.write("}\n") # End the JSON object
            print(f"\nPMTINFO data saved to: {args.output_pmtinfo_file} (custom format)")
        except IOError as e:
            print(f"Error saving PMTINFO file: {e}")

    # Prepare data for visualization functions
    pmt_data_for_vis = []
    if summary.get("total_pmts_placed", 0) > 0:
        num_pmts_vis = len(pmtinfo_data['x'])
        for i in range(num_pmts_vis):
            pmt_data_for_vis.append({
                "x": pmtinfo_data['x'][i], "y": pmtinfo_data['y'][i], "z": pmtinfo_data['z'][i],
                "dir_x": pmtinfo_data['dir_x'][i], "dir_y": pmtinfo_data['dir_y'][i], "dir_z": pmtinfo_data['dir_z'][i],
            })

    if args.visualization_type == "html" and summary.get("total_pmts_placed", 0) > 0 :
        print("\n--- Generating and Launching HTML 3D Visualization ---")
        html_content = generate_visualization_html(detector_dims, pmt_data_for_vis, args.pmt_physical_diameter)
        try:
            # Create a temporary HTML file to show the visualization
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html', encoding='utf-8') as tmp_file:
                tmp_file.write(html_content)
                tmp_file_path = tmp_file.name
            print(f"Temporary HTML visualization saved to: {tmp_file_path}")
            print("Opening in web browser...")
            webbrowser.open(f'file://{os.path.realpath(tmp_file_path)}')
            # Wait for user input before deleting the temporary file
            input("HTML Visualization launched. Press Enter to clean up temporary file and exit...\n"
                  "(If the browser didn't open, manually open the HTML file linked above.)\n")
        except Exception as e:
            print(f"Error generating or launching HTML visualization: {e}")
        finally:
            # Clean up the temporary file
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                try: 
                    os.remove(tmp_file_path)
                    print(f"Temporary file {tmp_file_path} removed.")
                except OSError as e: 
                    print(f"Error removing temporary file {tmp_file_path}: {e}")

    elif args.visualization_type == "matplotlib" and summary.get("total_pmts_placed", 0) > 0:
        print("\n--- Generating Matplotlib 3D Visualization ---")
        try:
            plot_matplotlib_visualization(detector_dims, pmt_data_for_vis, args.pmt_physical_diameter)
        except Exception as e:
            print(f"Error generating Matplotlib visualization: {e}")
            print("Please ensure you have Matplotlib and NumPy installed ('pip install matplotlib numpy').")
            
    elif summary.get("total_pmts_placed", 0) == 0 and args.visualization_type != "none":
        print("\n--- Visualization Skipped ---")
        print("No PMTs were placed, so visualization is not meaningful.")
    elif args.visualization_type == "none":
        print("\n--- Visualization Skipped (as requested) ---")

    print("\nScript finished.")

