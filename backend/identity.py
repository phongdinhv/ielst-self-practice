from typing import Annotated
from uuid import UUID

from fastapi import Depends

LOCAL_LEARNER = UUID("00000000-0000-4000-8000-000000000001")


def active_learner():
    return LOCAL_LEARNER


LearnerId = Annotated[UUID, Depends(active_learner)]
