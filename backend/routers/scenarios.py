from backend.models import _utcnow

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import (
    AudioCache,
    AudioGenerationResult,
    BatchEdgesUpdate,
    BatchNodesUpdate,
    Edge,
    Node,
    NodeSchema,
    Scenario,
    ScenarioCreate,
    ScenarioListItem,
    ScenarioResponse,
    ScenarioUpdate,
)

router = APIRouter()


def _node_to_schema(node: Node) -> NodeSchema:
    return NodeSchema(
        id=node.id,
        label=node.label,
        script=node.script,
        node_type=node.node_type,
        position_x=node.position_x,
        position_y=node.position_y,
        has_audio=node.audio_cache is not None and node.audio_cache.audio_data is not None,
    )


def _scenario_to_response(scenario: Scenario) -> ScenarioResponse:
    return ScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        twilio_phone_number=scenario.twilio_phone_number,
        nodes=[_node_to_schema(n) for n in scenario.nodes],
        edges=[
            {
                "id": e.id,
                "source_node_id": e.source_node_id,
                "target_node_id": e.target_node_id,
                "condition_label": e.condition_label,
            }
            for e in scenario.edges
        ],
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


# --- Scenario CRUD ---


@router.get("/scenarios", response_model=list[ScenarioListItem])
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scenario).order_by(Scenario.updated_at.desc())
    )
    return result.scalars().all()


@router.post("/scenarios", response_model=ScenarioResponse)
async def create_scenario(
    payload: ScenarioCreate, db: AsyncSession = Depends(get_db)
):
    scenario = Scenario(
        name=payload.name,
        description=payload.description,
        twilio_phone_number=payload.twilio_phone_number,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return _scenario_to_response(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int, db: AsyncSession = Depends(get_db)
):
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenario_to_response(scenario)


@router.put("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    db: AsyncSession = Depends(get_db),
):
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if payload.name is not None:
        scenario.name = payload.name
    if payload.description is not None:
        scenario.description = payload.description
    if payload.twilio_phone_number is not None:
        scenario.twilio_phone_number = payload.twilio_phone_number

    scenario.updated_at = _utcnow()
    await db.commit()
    await db.refresh(scenario)
    return _scenario_to_response(scenario)


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: int, db: AsyncSession = Depends(get_db)
):
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    await db.delete(scenario)
    await db.commit()
    return {"ok": True}


# --- Batch Node Update (diff-based) ---


@router.put("/scenarios/{scenario_id}/nodes")
async def batch_update_nodes(
    scenario_id: int,
    payload: BatchNodesUpdate,
    db: AsyncSession = Depends(get_db),
):
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    existing_nodes = {n.id: n for n in scenario.nodes}
    incoming_ids = {n.id for n in payload.nodes}

    # Delete removed nodes
    for node_id, node in existing_nodes.items():
        if node_id not in incoming_ids:
            await db.delete(node)

    # Update or insert nodes
    for node_data in payload.nodes:
        if node_data.id in existing_nodes:
            node = existing_nodes[node_data.id]
            node.label = node_data.label
            node.script = node_data.script
            node.node_type = node_data.node_type
            node.position_x = node_data.position_x
            node.position_y = node_data.position_y
        else:
            node = Node(
                id=node_data.id,
                scenario_id=scenario_id,
                label=node_data.label,
                script=node_data.script,
                node_type=node_data.node_type,
                position_x=node_data.position_x,
                position_y=node_data.position_y,
            )
            db.add(node)

    scenario.updated_at = _utcnow()
    await db.commit()
    return {"ok": True}


# --- Batch Edge Update (diff-based) ---


@router.put("/scenarios/{scenario_id}/edges")
async def batch_update_edges(
    scenario_id: int,
    payload: BatchEdgesUpdate,
    db: AsyncSession = Depends(get_db),
):
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    existing_edges = {e.id: e for e in scenario.edges}
    incoming_ids = {e.id for e in payload.edges}

    # Delete removed edges
    for edge_id, edge in existing_edges.items():
        if edge_id not in incoming_ids:
            await db.delete(edge)

    # Update or insert edges
    for edge_data in payload.edges:
        if edge_data.id in existing_edges:
            edge = existing_edges[edge_data.id]
            edge.source_node_id = edge_data.source_node_id
            edge.target_node_id = edge_data.target_node_id
            edge.condition_label = edge_data.condition_label
        else:
            edge = Edge(
                id=edge_data.id,
                scenario_id=scenario_id,
                source_node_id=edge_data.source_node_id,
                target_node_id=edge_data.target_node_id,
                condition_label=edge_data.condition_label,
            )
            db.add(edge)

    scenario.updated_at = _utcnow()
    await db.commit()
    return {"ok": True}


# --- Audio Generation ---


@router.post(
    "/scenarios/{scenario_id}/generate-audio",
    response_model=AudioGenerationResult,
)
async def generate_audio(
    scenario_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from backend.services.tts_service import generate_audio_for_scenario

    result = await generate_audio_for_scenario(scenario, db, settings, force=force)
    return result
