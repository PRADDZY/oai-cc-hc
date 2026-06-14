from rescue_swarm.data import (
    DatasetRole,
    PerceptionTask,
    get_dataset_manifest,
    iter_dataset_manifests,
)


def test_registry_encodes_dataset_training_boundaries() -> None:
    hand_labels = get_dataset_manifest("sen1floods11-hand")
    weak_masks = get_dataset_manifest("sen1floods11-weak")
    accessibility = get_dataset_manifest("spacenet8")
    floodnet = get_dataset_manifest("floodnet")
    victims = get_dataset_manifest("seadronessee-odv2")

    assert hand_labels.role is DatasetRole.PRIMARY
    assert hand_labels.task is PerceptionTask.FLOOD_SEGMENTATION
    assert weak_masks.role is DatasetRole.AUXILIARY_ONLY
    assert weak_masks.primary_metrics_allowed is False
    assert accessibility.role is DatasetRole.SEPARATE_TASK
    assert accessibility.task is PerceptionTask.INFRASTRUCTURE_ACCESSIBILITY
    assert floodnet.role is DatasetRole.OPTIONAL_BRANCH
    assert floodnet.modality == "UAV_RGB"
    assert victims.role is DatasetRole.AUXILIARY_ONLY
    assert victims.task is PerceptionTask.VICTIM_DETECTION


def test_registry_filter_keeps_optional_branches_opt_in() -> None:
    default_ids = {manifest.dataset_id for manifest in iter_dataset_manifests()}
    all_ids = {
        manifest.dataset_id
        for manifest in iter_dataset_manifests(include_optional=True)
    }

    assert "floodnet" not in default_ids
    assert "floodnet" in all_ids
    assert "sen1floods11-hand" in default_ids


def test_unknown_dataset_has_actionable_error() -> None:
    try:
        get_dataset_manifest("not-a-dataset")
    except KeyError as error:
        assert "Known dataset ids" in str(error)
    else:
        raise AssertionError("unknown dataset id should fail")
