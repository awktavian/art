from __future__ import annotations

"""Pydantic models for world generation API."""
from typing import Any

from pydantic import BaseModel, Field


class WorldGenRequest(BaseModel):
    """Request model for generating new world panoramas.

    Supports text-to-world or image-to-world generation with optional
    action sequences and templates.
    """

    prompt: str | None = Field(None, description="Text prompt for panorama generation")
    image_path: str | None = Field(None, description="Path to source image for panorama generation")
    labels_fg1: str | None = Field(
        None, description="Comma-separated foreground labels for first layer"
    )
    labels_fg2: str | None = Field(
        None, description="Comma-separated foreground labels for second layer"
    )
    classes: str | None = Field(
        None, description="Comma-separated object classes to include in scene"
    )
    action_list: list[str] | None = Field(
        default=None,
        description="Optional keyboard-like actions, e.g., ['w','a','d','s']",
    )
    action_speed_list: list[float] | None = Field(
        default=None,
        description="Optional speeds per action; must match action_list length",
    )
    template: str | None = Field(
        default=None,
        description="Optional template: rider|racer|scout|sniper|sail|stroll",
    )


class WorldGenResponse(BaseModel):
    """Response model for world generation request submission.

    Returns task identifier for async job tracking.
    """

    task_id: str = Field(..., description="Unique identifier for tracking generation job")
    status: str = Field(..., description="Initial job status (typically 'pending' or 'queued')")
    submitted_at: str = Field(..., description="ISO 8601 timestamp of request submission")


class WorldMotionRequest(BaseModel):
    """Request model for adding motion/animation to world session.

    Applies camera motion or object animation based on natural language prompt.
    """

    session_id: str = Field(..., description="Active world session identifier")
    prompt: str = Field(..., description="Natural language description of desired motion/animation")
    duration: float = Field(3.0, description="Duration of motion in seconds", ge=0.1, le=60.0)
    style: str | None = Field(
        None, description="Motion style hint (e.g., 'smooth', 'cinematic', 'fast')"
    )


class WorldMotionResponse(BaseModel):
    """Response model for world motion application.

    Reports success status and number of animation keyframes applied.
    """

    success: bool = Field(..., description="Whether motion was successfully applied")
    session_id: str = Field(..., description="World session identifier")
    applied_keyframes: int | None = Field(
        None, description="Number of animation keyframes generated"
    )
    error: str | None = Field(None, description="Error message if success=false")


class WorldJobResult(BaseModel):
    """Result model for completed world generation job.

    Contains world identifier, asset URLs, and generation metadata.
    """

    success: bool = Field(..., description="Whether generation completed successfully")
    world_id: str | None = Field(None, description="Unique identifier for generated world")
    panorama_url: str | None = Field(None, description="URL to generated panorama image")
    world_dir: str | None = Field(None, description="Filesystem path to world asset directory")
    metadata: dict[str, Any] | None = Field(
        None, description="Generation metadata (resolution, provider, etc.)"
    )
    error: str | None = Field(None, description="Error message if success=false")


class ComposeRequest(BaseModel):
    """Request model for composing world with characters and objects.

    Combines base world panorama with character models and object assets.
    """

    world_id: str = Field(..., description="Base world identifier")
    character_id: str = Field(..., description="Character model identifier to place in world")
    object_ids: list[str] = Field(
        default_factory=list, description="List of object asset IDs to add to scene"
    )
    style_profile: dict[str, Any] | None = Field(
        default=None,
        description="Lighting, post-processing, etc.",
    )


class ComposeResponse(BaseModel):
    """Response model for world composition operation.

    Returns new composed world identifier on success.
    """

    success: bool = Field(..., description="Whether composition completed successfully")
    composed_world_id: str | None = Field(None, description="Identifier for newly composed world")
    error: str | None = Field(None, description="Error message if success=false")


class AugmentRequest(BaseModel):
    """Request model for augmenting existing world with additional image.

    Adds new content to world using image-to-world synthesis.
    """

    world_id: str = Field(..., description="Existing world identifier to augment")
    image_path: str = Field(..., description="Path to augmentation source image")
    prompt: str | None = Field(None, description="Optional text prompt to guide augmentation")
    style: str = Field("photorealistic", description="Rendering style for augmentation")


class CreateWorldRequest(BaseModel):
    """Request model for creating new world from scratch.

    Supports text-to-world or image-to-world with custom dimensions.
    """

    prompt: str | None = Field(None, description="Text prompt for world generation")
    image_path: str | None = Field(None, description="Path to source image for world generation")
    style: str = Field(
        "photorealistic", description="Rendering style (photorealistic, stylized, etc.)"
    )
    dimensions: dict[str, float] | None = Field(
        None, description="Custom world dimensions {width, height, depth} in meters"
    )


class HoloportRequest(BaseModel):
    """Request model for teleporting entity between worlds.

    Transfers character or object from one world to another with optional repositioning.
    """

    entity_id: str = Field(..., description="Identifier of entity to teleport")
    entity_type: str = Field(..., description="Entity type: 'character' or 'object'")
    target_world_id: str = Field(..., description="Destination world identifier")
    position: dict[str, float] | None = Field(
        None, description="Optional spawn position {x, y, z} in target world"
    )


class AppManifestRequest(BaseModel):
    """Request model for registering application manifest in world.

    Links external application metadata to world for integration.
    """

    world_id: str = Field(..., description="World identifier to register app with")
    app_name: str = Field(..., description="Unique application name/identifier")
    manifest_data: dict[str, Any] = Field(..., description="Application manifest JSON data")


class AnchorUpsertRequest(BaseModel):
    """Request model for creating or updating spatial anchor.

    Anchors mark persistent spatial locations in world for AR/VR alignment.
    """

    world_id: str = Field(..., description="World identifier to place anchor in")
    anchor_id: str | None = Field(None, description="Existing anchor ID to update, or None for new")
    position: dict[str, float] = Field(
        ..., description="Anchor position {x, y, z} in world coordinates"
    )
    orientation: dict[str, float] | None = Field(
        None, description="Optional orientation quaternion {x, y, z, w}"
    )
    metadata: dict[str, Any] | None = Field(None, description="Optional anchor metadata/tags")


class WorldExportRequest(BaseModel):
    """Request model for exporting world to external format.

    Exports world geometry, materials, and animations to USD, glTF, or other formats.
    """

    world_id: str | None = Field(
        None, description="World identifier to export (mutually exclusive with session_id)"
    )
    session_id: str | None = Field(
        None, description="Session identifier to export (mutually exclusive with world_id)"
    )
    format: str = Field("usd", description="Export format: 'usd', 'gltf', 'fbx', 'obj'")
    include_materials: bool = Field(True, description="Whether to export material/texture data")
    include_animations: bool = Field(True, description="Whether to export animation/keyframe data")


class AddObjectRequest(BaseModel):
    """Request model for adding object to world session.

    Places object asset at specified position in active world.
    """

    object_id: str = Field(..., description="Object asset identifier to add")
    position: dict[str, float] | None = Field(
        None, description="Optional spawn position {x, y, z}, defaults to origin"
    )


class ApplySessionRequest(BaseModel):
    """Request model for applying operation to world session.

    Generic operation request for session state modifications.
    """

    operation: str = Field(
        ..., description="Operation type to apply (e.g., 'export', 'transform', 'filter')"
    )
    params: dict[str, Any] | None = Field(
        None, description="Operation-specific parameters dictionary"
    )


class ListSpacesResponse(BaseModel):
    """Response model for listing available world spaces.

    Returns paginated list of world space metadata.
    """

    spaces: list[dict[str, Any]] = Field(..., description="List of space metadata dictionaries")
    total: int = Field(..., description="Total number of spaces available (before pagination)")


class SessionStartRequest(BaseModel):
    """Request model for starting new world session.

    Creates interactive session with specified world, character, and rendering settings.
    """

    world_id: str = Field(..., description="World identifier to load into session")
    character_id: str | None = Field(None, description="Optional character to spawn in world")
    scene_type: str = Field(
        "character_studio",
        description="Scene preset: 'character_studio', 'open_world', 'cinematic'",
    )
    ambient_light: list[float] | None = Field(
        None, description="RGB ambient light color [0-1, 0-1, 0-1]"
    )
    background_color: list[float] | None = Field(
        None, description="RGB background color [0-1, 0-1, 0-1]"
    )
    visual_quality: str | None = Field(
        None, description="Rendering quality: 'low', 'medium', 'high', 'ultra'"
    )
    provider: str | None = Field(
        default=None, description="Preferred provider (emu, latticeworld, agentic, unrealzoo)"
    )
    use_unrealzoo: bool = Field(
        default=False, description="Use a predefined UnrealZoo evaluation environment"
    )


class SessionStartResponse(BaseModel):
    """Response from starting a world session."""

    session_id: str = Field(..., description="Unique session identifier")
    room_id: str | None = Field(None, description="Associated room identifier")
    provider: str | None = Field(None, description="Provider used for world generation")


class ApplySessionResponse(BaseModel):
    """Response from applying session operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    session_id: str = Field(..., description="Session identifier")
    export_path: str | None = Field(None, description="Path to exported session data")
    error: str | None = Field(None, description="Error message if operation failed")
