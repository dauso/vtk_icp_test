#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Reference: https://kitware.github.io/vtk-examples/site/Python/PolyData/AlignTwoPolyDatas/
'''

import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import vtkmodules.vtkInteractionStyle
# noinspection PyUnresolvedReferences
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import (
    VTK_DOUBLE_MAX,
    vtkPoints
)
from vtkmodules.vtkCommonCore import (
    VTK_VERSION_NUMBER,
    vtkVersion
)
from vtkmodules.vtkCommonDataModel import (
    vtkIterativeClosestPointTransform,
    vtkPolyData
)
from vtkmodules.vtkCommonTransforms import (
    vtkLandmarkTransform,
    vtkTransform
)
from vtkmodules.vtkFiltersGeneral import (
    vtkOBBTree,
    vtkTransformPolyDataFilter
)
from vtkmodules.vtkFiltersModeling import vtkHausdorffDistancePointSetFilter
from vtkmodules.vtkIOGeometry import vtkSTLReader
from vtkmodules.vtkInteractionWidgets import (
    vtkCameraOrientationWidget,
    vtkOrientationMarkerWidget
)
from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkDataSetMapper,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkRenderer
)


def get_program_parameters():
    import argparse
    description = 'How to align two vtkPolyData\'s.'
    epilogue = '''

    '''
    parser = argparse.ArgumentParser(description=description, epilog=epilogue,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('src_fn', help='The polydata source file name,e.g. thingiverse/Grey_Nurse_Shark.stl.')
    parser.add_argument('tgt_fn', help='The polydata target file name, e.g. greatWhite.stl.')

    args = parser.parse_args()

    return args.src_fn, args.tgt_fn


def main():
    colors = vtkNamedColors()

    src_fn, tgt_fn = get_program_parameters()
    print('Loading source:', src_fn)
    source_polydata = read_stl(src_fn)
    # Save the source polydata in case the alignment process does not improve
    # segmentation.
    original_source_polydata = vtkPolyData()
    original_source_polydata.DeepCopy(source_polydata)

    print('Loading target:', tgt_fn)
    target_polydata = read_stl(tgt_fn)

    # If the target orientation is markedly different, you may need to apply a
    # transform to orient the target with the source.
    # For example, when using Grey_Nurse_Shark.stl as the source and
    # greatWhite.stl as the target, you need to transform the target.
    trnf = vtkTransform()
    if Path(src_fn).name == 'Grey_Nurse_Shark.stl' and Path(tgt_fn).name == 'greatWhite.stl':
        trnf.RotateY(90)

    tpd = vtkTransformPolyDataFilter()
    tpd.SetTransform(trnf)
    tpd.SetInputData(target_polydata)
    tpd.Update()

    renderer = vtkRenderer()
    render_window = vtkRenderWindow()
    render_window.AddRenderer(renderer)
    interactor = vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)

    distance = vtkHausdorffDistancePointSetFilter()
    distance.SetInputData(0, tpd.GetOutput())
    distance.SetInputData(1, source_polydata)
    distance.Update()

    distance_before_align = distance.GetOutput(0).GetFieldData().GetArray('HausdorffDistance').GetComponent(0, 0)

    # Refine the alignment using IterativeClosestPoint.
    icp = vtkIterativeClosestPointTransform()
    icp.SetSource(source_polydata)
    icp.SetTarget(tpd.GetOutput())
    icp.GetLandmarkTransform().SetModeToRigidBody()
    icp.SetMaximumNumberOfLandmarks(100)
    icp.SetMaximumMeanDistance(.00001)
    icp.SetMaximumNumberOfIterations(500)
    icp.CheckMeanDistanceOn()
    icp.StartByMatchingCentroidsOn()
    icp.Update()
    icp_mean_distance = icp.GetMeanDistance()

    print()
    print("ICP Matrix\n")
    print(icp.GetMatrix())
    print("ICP Landmark Matrix\n")
    print(icp.GetLandmarkTransform().GetMatrix())
    print()

    lm_transform = icp.GetLandmarkTransform()
    transform = vtkTransformPolyDataFilter()
    transform.SetInputData(source_polydata)
    transform.SetTransform(lm_transform)
    transform.SetTransform(icp)
    transform.Update()

    distance.SetInputData(0, tpd.GetOutput())
    distance.SetInputData(1, transform.GetOutput())
    distance.Update()

    # Note: If there is an error extracting eigenfunctions, then this will be zero.
    distance_after_icp = distance.GetOutput(0).GetFieldData().GetArray('HausdorffDistance').GetComponent(0, 0)

    print('Distances:')
    print('  Before aligning:                        {:0.5f}'.format(distance_before_align))
    print('  Aligning using IterativeClosestPoint:   {:0.5f}'.format(distance_after_icp))

    # Select the source to use.
    source_mapper = vtkDataSetMapper()
    # source_mapper.SetInputData(source_polydata)
    source_mapper.SetInputConnection(transform.GetOutputPort())
    source_mapper.ScalarVisibilityOff()

    source_actor = vtkActor()
    source_actor.SetMapper(source_mapper)
    source_actor.GetProperty().SetOpacity(0.6)
    source_actor.GetProperty().SetDiffuseColor(
        colors.GetColor3d('White'))
    renderer.AddActor(source_actor)

    target_mapper = vtkDataSetMapper()
    target_mapper.SetInputData(tpd.GetOutput())
    target_mapper.ScalarVisibilityOff()

    target_actor = vtkActor()
    target_actor.SetMapper(target_mapper)
    target_actor.GetProperty().SetDiffuseColor(
        colors.GetColor3d('Tomato'))
    renderer.AddActor(target_actor)

    render_window.AddRenderer(renderer)
    renderer.SetBackground(colors.GetColor3d("sea_green_light"))
    renderer.UseHiddenLineRemovalOn()

    if vtkVersion.GetVTKMajorVersion() >= 9:
        try:
            cam_orient_manipulator = vtkCameraOrientationWidget()
            cam_orient_manipulator.SetParentRenderer(renderer)
            # Enable the widget.
            cam_orient_manipulator.On()
        except AttributeError:
            pass
    else:
        axes = vtkAxesActor()
        widget = vtkOrientationMarkerWidget()
        rgba = [0.0, 0.0, 0.0, 0.0]
        colors.GetColor("Carrot", rgba)
        widget.SetOutlineColor(rgba[0], rgba[1], rgba[2])
        widget.SetOrientationMarker(axes)
        widget.SetInteractor(interactor)
        widget.SetViewport(0.0, 0.0, 0.2, 0.2)
        widget.EnabledOn()
        widget.InteractiveOn()

    render_window.SetSize(640, 480)
    render_window.Render()
    render_window.SetWindowName('ICP_Test')

    interactor.Start()


def read_stl(file_name):
    reader = vtkSTLReader()
    reader.SetFileName(file_name)
    reader.Update()
    poly_data = reader.GetOutput()

    return poly_data


if __name__ == '__main__':
    main()
