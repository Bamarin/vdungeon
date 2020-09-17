﻿using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;

[CustomEditor(typeof(GridObject))]
public class GridObjectEditor : Editor
{

    public override void OnInspectorGUI()
    {
        GridObject castedTarget = (GridObject)target;

        EditorGUI.BeginChangeCheck();

        Vector2Int newGridPosition = EditorGUILayout.Vector2IntField("Grid Position: ", castedTarget.gridPosition);
        if (newGridPosition != castedTarget.gridPosition)
        {
            // This call also updates the object's position, and therefore must be placed after the check
            castedTarget.MoveToGridPosition(newGridPosition);
        }

        GridObject.Orientation newOrientation = (GridObject.Orientation)EditorGUILayout.EnumPopup("Grid Orientation: ", castedTarget.gridOrientation);
        if (newOrientation != castedTarget.gridOrientation)
        {
            // This call also updates the object's rotation, and therefore must be placed after the check
            castedTarget.MoveToGridOrientation(newOrientation);
        }

        if (GUILayout.Button("Snap to Grid"))
        {
            castedTarget.SnapToLocal();
            castedTarget.SnapToOrientation();
        }

        if (EditorGUI.EndChangeCheck() && !Application.isPlaying)
        {
            EditorUtility.SetDirty(castedTarget);
            EditorSceneManager.MarkSceneDirty(castedTarget.gameObject.scene);
        }

        serializedObject.ApplyModifiedProperties();
    }
}
