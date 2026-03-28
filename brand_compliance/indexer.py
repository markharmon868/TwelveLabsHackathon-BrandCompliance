import time
from pathlib import Path
from twelvelabs.indexes.types import IndexesCreateRequestModelsItem
from .client import get_client


# Models used for brand compliance analysis:
#   - marengo2.7  → visual + audio search (find relevant clips fast)
#   - pegasus1.2  → visual + audio generate (deep scene understanding)
_MODELS = [
    IndexesCreateRequestModelsItem(
        model_name="marengo2.7",
        model_options=["visual", "audio"],
    ),
    IndexesCreateRequestModelsItem(
        model_name="pegasus1.2",
        model_options=["visual", "audio"],
    ),
]

_POLL_INTERVAL = 10  # seconds between status checks


def create_index(index_name: str) -> str:
    """
    Create a new TwelveLabs index configured for brand compliance analysis.

    Returns the index_id of the newly created index.
    """
    client = get_client()
    response = client.indexes.create(
        index_name=index_name,
        models=_MODELS,
    )
    return response.id


def upload_video(index_id: str, video_path: str | Path) -> str:
    """
    Upload a video file to the given index and wait for indexing to complete.

    Returns the video_id assigned by TwelveLabs once ready.
    Raises RuntimeError if indexing fails.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    client = get_client()

    print(f"Uploading '{video_path.name}' to index {index_id}...")
    with video_path.open("rb") as f:
        task = client.tasks.create(
            index_id=index_id,
            video_file=f,
        )

    task_id = task.id
    print(f"Upload complete. Task ID: {task_id}. Waiting for indexing...")

    while True:
        status_response = client.tasks.retrieve(task_id)
        status = status_response.status

        if status == "ready":
            video_id = status_response.video_id
            print(f"Indexing complete. Video ID: {video_id}")
            return video_id

        if status == "failed":
            raise RuntimeError(
                f"Indexing task {task_id} failed. Check the TwelveLabs dashboard."
            )

        print(f"  Status: {status} — checking again in {_POLL_INTERVAL}s...")
        time.sleep(_POLL_INTERVAL)
