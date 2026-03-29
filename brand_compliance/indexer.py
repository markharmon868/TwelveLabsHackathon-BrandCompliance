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

_POLL_INTERVAL = 3  # seconds between status checks


def create_index(index_name: str, api_key: str | None = None) -> str:
    """
    Create a new TwelveLabs index configured for brand compliance analysis.
    If an index with the same name already exists, returns its ID instead.

    Returns the index_id.
    """
    client = get_client(api_key)

    # Check for an existing index with this name to avoid 409 errors on re-runs
    existing = list(client.indexes.list(index_name=index_name, page_limit=1))
    if existing:
        index_id = existing[0].id
        print(f"Reusing existing index '{index_name}' ({index_id})")
        return index_id

    response = client.indexes.create(
        index_name=index_name,
        models=_MODELS,
    )
    return response.id


def upload_video(index_id: str, video_path: str | Path, api_key: str | None = None) -> str:
    """
    Upload a video file to the given index and wait for indexing to complete.

    Returns the video_id assigned by TwelveLabs once ready.
    Raises RuntimeError if indexing fails.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    client = get_client(api_key)

    print(f"Uploading '{video_path.name}' to index {index_id}...")
    with video_path.open("rb") as f:
        task = client.tasks.create(
            index_id=index_id,
            video_file=f,
        )

    print(f"Upload complete. Task ID: {task.id}. Waiting for indexing...")

    task = client.tasks.wait_for_done(task.id, sleep_interval=_POLL_INTERVAL)

    if task.status == "failed":
        raise RuntimeError(
            f"Indexing task {task.id} failed. Check the TwelveLabs dashboard."
        )

    print(f"Indexing complete. Video ID: {task.video_id}")
    return task.video_id
