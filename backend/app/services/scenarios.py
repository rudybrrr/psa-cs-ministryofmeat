import random

from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    NamedFactor,
    ScenarioAssumptions,
    ScenarioSet,
    ScenarioWorld,
)


DEFAULT_SEED = 20260822
DEFAULT_WORLD_COUNT = 50
SHARED_STD_MINUTES = 12.0
HANDLING_GROUP_STD_MINUTES = 7.0
CONTAINER_NOISE_STD_MINUTES = 2.0


class SeededScenarioGenerator:
    def generate(
        self,
        fixture: CanonicalIncidentFixture,
        *,
        seed: int = DEFAULT_SEED,
        world_count: int = DEFAULT_WORLD_COUNT,
    ) -> ScenarioSet:
        if world_count <= 0 or world_count % 2 != 0:
            raise ValueError("world_count must be a positive even integer")

        random_source = random.Random(seed)
        handling_group_ids = sorted(
            {profile.handling_group_id for profile in fixture.profiles}
        )
        container_ids = sorted(profile.container.id for profile in fixture.profiles)
        half_world_count = world_count // 2
        base_worlds: list[ScenarioWorld] = []
        mirror_worlds: list[ScenarioWorld] = []

        for index in range(half_world_count):
            shared = int(round(random_source.gauss(0.0, SHARED_STD_MINUTES)))
            groups = tuple(
                NamedFactor(
                    key=key,
                    minutes=int(
                        round(
                            random_source.gauss(
                                0.0,
                                HANDLING_GROUP_STD_MINUTES,
                            )
                        )
                    ),
                )
                for key in handling_group_ids
            )
            noise = tuple(
                NamedFactor(
                    key=key,
                    minutes=int(
                        round(
                            random_source.gauss(
                                0.0,
                                CONTAINER_NOISE_STD_MINUTES,
                            )
                        )
                    ),
                )
                for key in container_ids
            )

            base_worlds.append(
                ScenarioWorld(
                    index=index,
                    shared_discharge_factor_minutes=shared,
                    handling_group_factors=groups,
                    container_noise_factors=noise,
                )
            )
            mirror_worlds.append(
                ScenarioWorld(
                    index=index + half_world_count,
                    shared_discharge_factor_minutes=-shared,
                    handling_group_factors=tuple(
                        NamedFactor(key=factor.key, minutes=-factor.minutes)
                        for factor in groups
                    ),
                    container_noise_factors=tuple(
                        NamedFactor(key=factor.key, minutes=-factor.minutes)
                        for factor in noise
                    ),
                )
            )

        return ScenarioSet(
            assumptions=ScenarioAssumptions(
                seed=seed,
                world_count=world_count,
                shared_std_minutes=SHARED_STD_MINUTES,
                handling_group_std_minutes=HANDLING_GROUP_STD_MINUTES,
                container_noise_std_minutes=CONTAINER_NOISE_STD_MINUTES,
                antithetic_pairs=True,
            ),
            worlds=tuple(base_worlds + mirror_worlds),
        )
