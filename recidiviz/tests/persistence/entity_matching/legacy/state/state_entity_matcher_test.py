# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2019 Recidiviz, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================
"""Tests for state_entity_matcher.py."""
import datetime
import unittest
from typing import Any, List, Tuple

import attr
from mock import patch
from more_itertools import one

from recidiviz.common.constants.state.state_case_type import StateSupervisionCaseType
from recidiviz.common.constants.state.state_charge import StateChargeStatus
from recidiviz.common.constants.state.state_person import (
    StateEthnicity,
    StateGender,
    StateRace,
)
from recidiviz.common.constants.state.state_sentence import StateSentenceStatus
from recidiviz.common.constants.state.state_staff_role_period import StateStaffRoleType
from recidiviz.common.constants.state.state_supervision_violated_condition import (
    StateSupervisionViolatedConditionType,
)
from recidiviz.common.constants.state.state_supervision_violation import (
    StateSupervisionViolationType,
)
from recidiviz.common.constants.state.state_supervision_violation_response import (
    StateSupervisionViolationResponseDecision,
)
from recidiviz.common.ingest_metadata import IngestMetadata
from recidiviz.persistence.database.schema.state import schema
from recidiviz.persistence.database.schema_type import SchemaType
from recidiviz.persistence.database.session import Session
from recidiviz.persistence.database.sqlalchemy_database_key import SQLAlchemyDatabaseKey
from recidiviz.persistence.entity.state.entities import (
    StateAssessment,
    StateCharge,
    StateIncarcerationIncident,
    StateIncarcerationIncidentOutcome,
    StateIncarcerationPeriod,
    StateIncarcerationSentence,
    StatePerson,
    StatePersonAlias,
    StatePersonEthnicity,
    StatePersonExternalId,
    StatePersonRace,
    StateStaff,
    StateStaffExternalId,
    StateStaffRolePeriod,
    StateSupervisionCaseTypeEntry,
    StateSupervisionPeriod,
    StateSupervisionSentence,
    StateSupervisionViolatedConditionEntry,
    StateSupervisionViolation,
    StateSupervisionViolationResponse,
    StateSupervisionViolationResponseDecisionEntry,
    StateSupervisionViolationTypeEntry,
)
from recidiviz.persistence.entity_matching.legacy import entity_matching
from recidiviz.persistence.entity_matching.legacy.entity_matching_types import (
    MatchedEntities,
)
from recidiviz.persistence.entity_matching.legacy.state import state_entity_matcher
from recidiviz.persistence.entity_matching.legacy.state.state_entity_matcher import (
    MAX_NUM_TREES_TO_SEARCH_FOR_NON_PLACEHOLDER_TYPES,
    StateEntityMatcher,
)
from recidiviz.persistence.entity_matching.legacy.state.state_specific_entity_matching_delegate import (
    StateSpecificEntityMatchingDelegate,
)
from recidiviz.persistence.errors import EntityMatchingError
from recidiviz.persistence.persistence_utils import (
    EntityDeserializationResult,
    RootEntityT,
    SchemaRootEntityT,
)
from recidiviz.tests.persistence.database.schema.state.schema_test_utils import (
    generate_alias,
    generate_assessment,
    generate_charge,
    generate_ethnicity,
    generate_incarceration_incident,
    generate_incarceration_period,
    generate_incarceration_sentence,
    generate_person,
    generate_person_external_id,
    generate_race,
    generate_supervision_case_type_entry,
    generate_supervision_period,
    generate_supervision_sentence,
    generate_supervision_violated_condition_entry,
    generate_supervision_violation,
    generate_supervision_violation_response,
    generate_supervision_violation_response_decision_entry,
    generate_supervision_violation_type_entry,
)
from recidiviz.tests.persistence.entity_matching.legacy.state.base_state_entity_matcher_test_classes import (
    BaseStateEntityMatcherTest,
)

_EXTERNAL_ID = "EXTERNAL_ID-1"
_EXTERNAL_ID_2 = "EXTERNAL_ID-2"
_EXTERNAL_ID_3 = "EXTERNAL_ID-3"
_EXTERNAL_ID_4 = "EXTERNAL_ID-4"
_EXTERNAL_ID_5 = "EXTERNAL_ID-5"
_EXTERNAL_ID_6 = "EXTERNAL_ID-6"
_ID_TYPE = "ID_TYPE"
_ID_TYPE_ANOTHER = "ID_TYPE_ANOTHER"
_FULL_NAME = "FULL_NAME"
_FULL_NAME_ANOTHER = "FULL_NAME_ANOTHER"
_COUNTY_CODE = "Iredell"
_STATE_CODE = "US_XX"
_DATE_1 = datetime.date(year=2019, month=1, day=1)
_DATE_2 = datetime.date(year=2019, month=2, day=1)
_DATE_3 = datetime.date(year=2019, month=3, day=1)


class TestStateEntityMatching(BaseStateEntityMatcherTest):
    """Tests for default state entity matching logic."""

    default_metadata: IngestMetadata

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TestStateEntityMatching.default_metadata = IngestMetadata(
            region="us_xx",
            ingest_time=datetime.datetime(year=1000, month=1, day=1),
            database_key=SQLAlchemyDatabaseKey.canonical_for_schema(
                schema_type=SchemaType.STATE
            ),
        )

    def setUp(self) -> None:
        super().setUp()
        self.matching_delegate_patcher = patch(
            "recidiviz.persistence.entity_matching.legacy.state."
            "state_specific_entity_matching_delegate_factory.StateSpecificEntityMatchingDelegateFactory."
            "build",
            new=self._get_base_delegate,
        )
        self.matching_delegate_patcher.start()
        self.addCleanup(self.matching_delegate_patcher.stop)

    def _get_base_delegate(self, **_kwargs: Any) -> StateSpecificEntityMatchingDelegate:
        return StateSpecificEntityMatchingDelegate(
            _STATE_CODE, TestStateEntityMatching.default_metadata
        )

    @staticmethod
    def _match(
        session: Session, ingested_root_entities: List[RootEntityT]
    ) -> MatchedEntities[SchemaRootEntityT]:
        deserialization_result = EntityDeserializationResult(
            root_entities=ingested_root_entities,
            enum_parsing_errors=0,
            general_parsing_errors=0,
            protected_class_errors=0,
        )
        return entity_matching.match(
            session=session,
            region=_STATE_CODE,
            ingested_root_entities=deserialization_result.root_entities,
            root_entity_cls=deserialization_result.root_entity_cls,
            schema_root_entity_cls=deserialization_result.schema_root_entity_cls,
            ingest_metadata=TestStateEntityMatching.default_metadata,
        )

    def test_match_newPerson(self) -> None:
        # Arrange 1 - Match
        db_person = schema.StatePerson(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_external_id = schema.StatePersonExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        db_person.external_ids = [db_external_id]
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        external_id_2 = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
        )
        person_2 = StatePerson.new_with_defaults(
            full_name=_FULL_NAME, external_ids=[external_id_2], state_code=_STATE_CODE
        )

        expected_db_person = entity_person
        expected_person_2 = attr.evolve(person_2)

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person_2])

        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person_2],
            matched_entities.root_entities,
            session,
            expected_unmatched_db_root_entities=[expected_db_person],
        )
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assert_no_errors(matched_entities)

    def test_match_newStaff(self) -> None:
        # Arrange 1 - Match
        db_staff = schema.StateStaff(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_external_id = schema.StateStaffExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        db_staff.external_ids = [db_external_id]
        entity_staff = self.to_entity(db_staff, StateStaff)

        self._commit_to_db(db_staff)

        external_id_2 = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
        )
        staff_2 = StateStaff.new_with_defaults(
            full_name=_FULL_NAME, external_ids=[external_id_2], state_code=_STATE_CODE
        )

        expected_db_staff = entity_staff
        expected_db_staff_2 = attr.evolve(staff_2)

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [staff_2])

        self.assert_root_entities_match_pre_and_post_commit(
            [expected_db_staff_2],
            matched_entities.root_entities,
            session,
            expected_unmatched_db_root_entities=[expected_db_staff],
        )
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assert_no_errors(matched_entities)

    def test_match_twoMatchingIngestedPersons(self) -> None:
        # Arrange
        external_id = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        external_id_2 = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE_ANOTHER
        )
        external_id_dup = attr.evolve(external_id)
        external_id_3 = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE_ANOTHER
        )
        person = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id, external_id_2],
            state_code=_STATE_CODE,
        )
        person_2 = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id_dup, external_id_3],
            state_code=_STATE_CODE,
        )

        expected_external_id_1 = attr.evolve(external_id)
        expected_external_id_2 = attr.evolve(external_id_2)
        expected_external_id_3 = attr.evolve(external_id_3)
        expected_person = attr.evolve(
            person,
            external_ids=[
                expected_external_id_1,
                expected_external_id_2,
                expected_external_id_3,
            ],
        )

        # Act
        session = self._session()
        matched_entities = self._match(session, [person, person_2])

        # Assert
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_match_twoMatchingIngestedStaff(self) -> None:
        # Arrange
        external_id = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        external_id_2 = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE_ANOTHER
        )
        external_id_dup = attr.evolve(external_id)
        external_id_3 = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE_ANOTHER
        )
        staff = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id, external_id_2],
            state_code=_STATE_CODE,
        )
        staff_2 = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id_dup, external_id_3],
            state_code=_STATE_CODE,
        )

        expected_external_id_1 = attr.evolve(external_id)
        expected_external_id_2 = attr.evolve(external_id_2)
        expected_external_id_3 = attr.evolve(external_id_3)
        expected_staff = attr.evolve(
            staff,
            external_ids=[
                expected_external_id_1,
                expected_external_id_2,
                expected_external_id_3,
            ],
        )

        # Act
        session = self._session()
        matched_entities = self._match(session, [staff, staff_2])

        # Assert
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_staff], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_match_twoMatchingIngestedPersons_with_children(self) -> None:
        # Arrange
        external_id = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        external_id_dup = attr.evolve(external_id)

        assessment = StateAssessment.new_with_defaults(
            state_code=_STATE_CODE, external_id="1"
        )
        assessment_dup = attr.evolve(assessment)
        assessment2 = StateAssessment.new_with_defaults(
            state_code=_STATE_CODE, external_id="2"
        )
        assessment3 = StateAssessment.new_with_defaults(
            state_code=_STATE_CODE, external_id="3"
        )

        person = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id],
            assessments=[assessment, assessment2],
            state_code=_STATE_CODE,
        )

        person_2 = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id_dup],
            assessments=[assessment_dup, assessment3],
            state_code=_STATE_CODE,
        )

        expected_external_id_1 = attr.evolve(external_id)
        expected_assessment_1 = attr.evolve(assessment)
        expected_assessment_2 = attr.evolve(assessment2)
        expected_assessment_3 = attr.evolve(assessment3)
        expected_person = attr.evolve(
            person,
            external_ids=[
                expected_external_id_1,
            ],
            assessments=[
                expected_assessment_1,
                expected_assessment_2,
                expected_assessment_3,
            ],
        )
        self.maxDiff = None
        # Act
        session = self._session()
        matched_entities = self._match(session, [person, person_2])

        # Assert
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_match_twoMatchingIngestedStaff_with_children(self) -> None:
        # Arrange
        external_id = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        external_id_dup = attr.evolve(external_id)

        role_period = StateStaffRolePeriod.new_with_defaults(
            state_code=_STATE_CODE,
            external_id="1",
            start_date=_DATE_1,
            end_date=_DATE_2,
            role_type=StateStaffRoleType.SUPERVISION_OFFICER,
        )
        role_period_dup = attr.evolve(role_period)
        role_period2 = StateStaffRolePeriod.new_with_defaults(
            state_code=_STATE_CODE,
            external_id="2",
            start_date=_DATE_2,
            end_date=_DATE_3,
            role_type=StateStaffRoleType.SUPERVISION_OFFICER,
        )
        role_period3 = StateStaffRolePeriod.new_with_defaults(
            state_code=_STATE_CODE,
            external_id="3",
            start_date=_DATE_3,
            role_type=StateStaffRoleType.SUPERVISION_OFFICER,
        )

        staff = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id],
            role_periods=[role_period, role_period2],
            state_code=_STATE_CODE,
        )

        staff_2 = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id_dup],
            role_periods=[role_period_dup, role_period3],
            state_code=_STATE_CODE,
        )

        expected_external_id_1 = attr.evolve(external_id)
        expected_role_period_1 = attr.evolve(role_period)
        expected_role_period_2 = attr.evolve(role_period2)
        expected_role_period_3 = attr.evolve(role_period3)
        expected_staff = attr.evolve(
            staff,
            external_ids=[
                expected_external_id_1,
            ],
            role_periods=[
                expected_role_period_1,
                expected_role_period_2,
                expected_role_period_3,
            ],
        )

        # Act
        session = self._session()
        matched_entities = self._match(session, [staff, staff_2])

        # Assert
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_staff], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_match_MatchingIngestedPersons_with_children_perf(self) -> None:
        # Arrange
        people = []
        incidents = []
        for i in range(1000):
            external_id = StatePersonExternalId.new_with_defaults(
                state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
            )

            incident = StateIncarcerationIncident.new_with_defaults(
                state_code=_STATE_CODE,
                external_id=f"{i}",
                incarceration_incident_outcomes=[
                    StateIncarcerationIncidentOutcome.new_with_defaults(
                        state_code=_STATE_CODE,
                        external_id=f"{i}",
                    )
                ],
            )
            incidents.append(incident)

            people.append(
                StatePerson.new_with_defaults(
                    full_name=_FULL_NAME,
                    external_ids=[external_id],
                    incarceration_incidents=[incident],
                    state_code=_STATE_CODE,
                )
            )

        expected_person = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[
                StatePersonExternalId.new_with_defaults(
                    state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
                )
            ],
            incarceration_incidents=incidents,
            state_code=_STATE_CODE,
        )

        # Act
        session = self._session()
        start = datetime.datetime.now()
        matched_entities = self._match(session, people)
        end = datetime.datetime.now()
        duration_seconds = (end - start).total_seconds()
        self.assertTrue(
            duration_seconds < 10, f"Runtime [{duration_seconds}] not below threshold"
        )

        # Assert
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_match_noPlaceholders_simplePeople(self) -> None:
        # Arrange 1 - Match
        db_person = schema.StatePerson(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_external_id = schema.StatePersonExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        db_person.external_ids = [db_external_id]

        self._commit_to_db(db_person)

        external_id = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        external_id_2 = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
        )
        person = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id, external_id_2],
            state_code=_STATE_CODE,
        )

        expected_person = attr.evolve(
            person,
            external_ids=[
                attr.evolve(
                    external_id,
                ),
                external_id_2,
            ],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )

    def test_match_simpleStaff(self) -> None:
        # Arrange 1 - Match
        db_staff = schema.StateStaff(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_external_id = schema.StateStaffExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        db_staff.external_ids = [db_external_id]

        self._commit_to_db(db_staff)

        external_id = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        external_id_2 = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
        )
        staff = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id, external_id_2],
            state_code=_STATE_CODE,
        )

        expected_staff = attr.evolve(
            staff,
            external_ids=[
                attr.evolve(
                    external_id,
                ),
                external_id_2,
            ],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [staff])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_staff], matched_entities.root_entities, session
        )

    def test_match_PersonWithChildren_success(self) -> None:
        # Arrange 1 - Match
        db_person = schema.StatePerson(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_incarceration_sentence = schema.StateIncarcerationSentence(
            person=db_person,
            status=StateSentenceStatus.EXTERNAL_UNKNOWN.value,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            county_code="county_code",
        )
        db_external_id = schema.StatePersonExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )

        db_person.incarceration_sentences = [db_incarceration_sentence]
        db_person.external_ids = [db_external_id]

        db_external_id_another = schema.StatePersonExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            id_type=_ID_TYPE,
        )
        db_person_another = schema.StatePerson(
            full_name=_FULL_NAME,
            external_ids=[db_external_id_another],
            state_code=_STATE_CODE,
        )
        self._commit_to_db(db_person, db_person_another)

        new_charge = StateCharge.new_with_defaults(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            status=StateChargeStatus.PRESENT_WITHOUT_INFO,
        )
        incarceration_sentence = StateIncarcerationSentence.new_with_defaults(
            state_code=_STATE_CODE,
            status=StateSentenceStatus.EXTERNAL_UNKNOWN,
            external_id=_EXTERNAL_ID,
            county_code="county_code-updated",
            charges=[new_charge],
        )
        external_id = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        person = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id],
            incarceration_sentences=[incarceration_sentence],
            state_code=_STATE_CODE,
        )

        external_id_another = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
        )
        person_another = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id_another],
            state_code=_STATE_CODE,
        )

        expected_person = attr.evolve(person, external_ids=[])
        expected_charge = attr.evolve(new_charge)
        expected_incarceration_sentence = attr.evolve(
            incarceration_sentence,
            charges=[expected_charge],
        )
        expected_external_id = attr.evolve(
            external_id,
        )
        expected_person.incarceration_sentences = [expected_incarceration_sentence]
        expected_person.external_ids = [expected_external_id]

        expected_person_another = attr.evolve(person_another)
        expected_external_id = attr.evolve(external_id_another)
        expected_person_another.external_ids = [expected_external_id]

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person, person_another])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assertEqual(2, matched_entities.total_root_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person, expected_person_another],
            matched_entities.root_entities,
            session,
        )

    def test_match_StaffWithChildren_success(self) -> None:
        # Arrange 1 - Match
        db_staff = schema.StateStaff(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_role_period = schema.StateStaffRolePeriod(
            state_code=_STATE_CODE,
            external_id="1",
            start_date=_DATE_1,
            end_date=_DATE_2,
            role_type=StateStaffRoleType.SUPERVISION_OFFICER.value,
        )
        db_external_id = schema.StateStaffExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )

        db_staff.role_periods = [db_role_period]
        db_staff.external_ids = [db_external_id]

        db_external_id_another = schema.StateStaffExternalId(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            id_type=_ID_TYPE,
        )
        db_staff_another = schema.StateStaff(
            full_name=_FULL_NAME,
            external_ids=[db_external_id_another],
            state_code=_STATE_CODE,
        )
        self._commit_to_db(db_staff, db_staff_another)

        role_period = StateStaffRolePeriod.new_with_defaults(
            state_code=_STATE_CODE,
            external_id="1",
            start_date=_DATE_1,
            end_date=_DATE_2,
            role_type=StateStaffRoleType.SUPERVISION_OFFICER,
        )
        new_role_period = StateStaffRolePeriod.new_with_defaults(
            state_code=_STATE_CODE,
            external_id="2",
            start_date=_DATE_2,
            end_date=_DATE_3,
            role_type=StateStaffRoleType.SUPERVISION_OFFICER,
        )
        external_id = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        staff = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id],
            role_periods=[role_period, new_role_period],
            state_code=_STATE_CODE,
        )

        external_id_another = StateStaffExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
        )
        staff_another = StateStaff.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id_another],
            state_code=_STATE_CODE,
        )

        expected_staff = attr.evolve(staff, external_ids=[])
        expected_role_period_2 = attr.evolve(new_role_period)
        expected_role_period = attr.evolve(
            role_period,
        )
        expected_external_id = attr.evolve(
            external_id,
        )
        expected_staff.role_periods = [expected_role_period, expected_role_period_2]
        expected_staff.external_ids = [expected_external_id]

        expected_staff_another = attr.evolve(staff_another)
        expected_external_id = attr.evolve(external_id_another)
        expected_staff_another.external_ids = [expected_external_id]

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [staff, staff_another])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assertEqual(2, matched_entities.total_root_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_staff, expected_staff_another],
            matched_entities.root_entities,
            session,
        )

    def test_match_ErrorMergingIngestedEntities(self) -> None:
        # Arrange 1 - Match
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person = generate_person(
            external_ids=[db_external_id], state_code=_STATE_CODE
        )
        entity_person = self.to_entity(db_person, StatePerson)

        db_external_id_2 = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            id_type=_ID_TYPE,
        )
        entity_external_id_2 = self.to_entity(db_external_id_2, StatePersonExternalId)
        db_incarceration_sentence = generate_incarceration_sentence(
            person=db_person, external_id=_EXTERNAL_ID
        )
        entity_incarceration_sentence = self.to_entity(
            db_incarceration_sentence, StateIncarcerationSentence
        )
        db_person_2 = generate_person(
            incarceration_sentences=[db_incarceration_sentence],
            external_ids=[db_external_id_2],
            state_code=_STATE_CODE,
        )
        entity_person_2 = self.to_entity(db_person_2, StatePerson)

        self._commit_to_db(db_person, db_person_2)

        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = attr.evolve(entity_person, person_id=None, external_ids=[external_id])

        incarceration_sentence = attr.evolve(
            entity_incarceration_sentence, incarceration_sentence_id=None
        )
        incarceration_sentence_dup = attr.evolve(
            incarceration_sentence, county_code=_COUNTY_CODE
        )
        external_id_2 = attr.evolve(entity_external_id_2, person_external_id_id=None)
        person_2 = attr.evolve(
            entity_person_2,
            person_id=None,
            external_ids=[external_id_2],
            incarceration_sentences=[
                incarceration_sentence,
                incarceration_sentence_dup,
            ],
        )

        # Act 1 - Match
        session = self._session()
        with self.assertRaisesRegex(
            EntityMatchingError,
            r"Found multiple different ingested entities of type \[StateIncarcerationSentence\] "
            r"with conflicting information",
        ):
            _ = self._match(session, [person, person_2])

    def test_matchPersons_multipleIngestedPeopleMatchOneDbPerson(self) -> None:
        db_external_id = generate_person_external_id(
            external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_external_id_2 = generate_person_external_id(
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE_ANOTHER,
        )
        entity_external_id_2 = self.to_entity(db_external_id_2, StatePersonExternalId)
        db_person = generate_person(
            full_name=_FULL_NAME,
            external_ids=[db_external_id, db_external_id_2],
            state_code=_STATE_CODE,
        )
        entity_person = self.to_entity(db_person, StatePerson)
        self._commit_to_db(db_person)
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        race_1 = StatePersonRace.new_with_defaults(
            state_code=_STATE_CODE, race=StateRace.WHITE
        )
        person = attr.evolve(
            entity_person,
            person_id=None,
            races=[race_1],
            external_ids=[external_id],
        )
        race_2 = StatePersonRace.new_with_defaults(
            state_code=_STATE_CODE, race=StateRace.OTHER
        )
        external_id_2 = attr.evolve(entity_external_id_2, person_external_id_id=None)
        person_dup = attr.evolve(
            person, races=[race_2], external_ids=[attr.evolve(external_id_2)]
        )

        expected_external_id = attr.evolve(
            external_id,
        )
        expected_external_id_2 = attr.evolve(external_id_2)
        expected_race_1 = attr.evolve(race_1)
        expected_race_2 = attr.evolve(race_2)
        expected_person = attr.evolve(
            person,
            races=[expected_race_1, expected_race_2],
            external_ids=[expected_external_id, expected_external_id_2],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person, person_dup])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assertEqual(2, matched_entities.total_root_entities)
        self.assert_no_errors(matched_entities)

    def test_matchPersons_replaceSingularChildFromMatchedParent(self) -> None:
        """Tests that if we have a singular placeholder child in the DB, we properly update
        that child entity to no longer be a placeholder in the case that we have match an ingested parent with a
        non-placeholder child.
        """
        # When our DB is in a strange state and has an entity has a singluar placeholder child, we throw an error
        # when that child entity is updated. This test has logic that needs to be uncommented once this bug is resolved.
        # Arrange 1 - Match
        db_person = generate_person(state_code=_STATE_CODE)
        db_charge = generate_charge(
            person=db_person,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateChargeStatus.PRESENT_WITHOUT_INFO.value,
        )
        entity_charge = self.to_entity(db_charge, StateCharge)
        db_supervision_sentence = generate_supervision_sentence(
            person=db_person,
            status=StateSentenceStatus.SERVING.value,
            external_id=_EXTERNAL_ID,
            charges=[db_charge],
            state_code=_STATE_CODE,
        )
        entity_supervision_sentence = self.to_entity(
            db_supervision_sentence, StateSupervisionSentence
        )
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person.supervision_sentences = [db_supervision_sentence]
        db_person.external_ids = [db_external_id]
        entity_person = self.to_entity(db_person, StatePerson)
        self._commit_to_db(db_person)

        charge = attr.evolve(
            entity_charge,
            charge_id=None,
            external_id=_EXTERNAL_ID,
        )
        sentence = attr.evolve(
            entity_supervision_sentence,
            supervision_sentence_id=None,
            charges=[charge],
        )
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id],
            supervision_sentences=[sentence],
        )

        expected_charge = attr.evolve(entity_charge)
        expected_supervision_sentence = attr.evolve(
            entity_supervision_sentence, charges=[expected_charge]
        )
        expected_external_id = attr.evolve(entity_external_id)
        expected_person = attr.evolve(
            entity_person,
            external_ids=[expected_external_id],
            supervision_sentences=[expected_supervision_sentence],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assertEqual(0, matched_entities.error_count)
        self.assertEqual(0, matched_entities.database_cleanup_error_count)

    def test_ingestedTreeHasDuplicateEntitiesInParentsAndChildrenEntities(self) -> None:
        """This tests an edge case in the interaction of `merge_multiparent_entities` and
        `_merge_new_parent_child_links`. Here we ingest duplicate supervision sentences with duplicate charge children.
        In entity matching, the charge children get merged by `merge_multiparent_entities`, and the
        supervision sentences get merged as a part of `merge_new_parent_child_links`. This test ensures that in
        this second step, we do NOT accidentally make the charge children placeholder objects.
        """
        # Arrange 1 - Match
        external_id = StatePersonExternalId.new_with_defaults(
            external_id=_EXTERNAL_ID, id_type=_ID_TYPE, state_code=_STATE_CODE
        )
        charge = StateCharge.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateChargeStatus.DROPPED,
        )
        charge_dup = attr.evolve(charge)
        supervision_sentence = StateSupervisionSentence.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge],
        )
        supervision_sentence_dup = attr.evolve(
            supervision_sentence, charges=[charge_dup]
        )
        person = StatePerson.new_with_defaults(
            full_name=_FULL_NAME,
            external_ids=[external_id],
            supervision_sentences=[supervision_sentence, supervision_sentence_dup],
            state_code=_STATE_CODE,
        )

        expected_charge = attr.evolve(charge)
        expected_supervision_sentence = attr.evolve(
            supervision_sentence, charges=[expected_charge]
        )
        expected_external_id = attr.evolve(external_id)
        expected_person = attr.evolve(
            person,
            supervision_sentences=[expected_supervision_sentence],
            external_ids=[expected_external_id],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )

    def test_matchPersons_matchesTwoDbPeople_mergeDbPeopleMoveChildren(self) -> None:
        """Tests that our system correctly handles the situation where we have
        2 distinct people in our DB, but we learn the two DB people should be
        merged into 1 person based on a new ingested person. Here the two DB
        people to merge have distinct DB children.
        """
        # Arrange 1 - Match
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_external_id_2 = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            id_type=_ID_TYPE_ANOTHER,
        )
        entity_external_id_2 = self.to_entity(db_external_id_2, StatePersonExternalId)
        db_person = generate_person(
            full_name=_FULL_NAME,
            external_ids=[db_external_id],
            state_code=_STATE_CODE,
        )
        entity_person = self.to_entity(db_person, StatePerson)

        db_person_2 = generate_person(
            full_name=_FULL_NAME,
            external_ids=[db_external_id_2],
            state_code=_STATE_CODE,
        )
        db_incarceration_sentence = generate_incarceration_sentence(
            person=db_person_2, external_id=_EXTERNAL_ID
        )
        db_person_2.incarceration_sentences = [db_incarceration_sentence]
        entity_incarceration_sentence = self.to_entity(
            db_incarceration_sentence, StateIncarcerationSentence
        )

        self._commit_to_db(db_person, db_person_2)

        race = StatePersonRace.new_with_defaults(
            state_code=_STATE_CODE, race=StateRace.BLACK
        )
        alias = StatePersonAlias.new_with_defaults(
            state_code=_STATE_CODE, full_name=_FULL_NAME_ANOTHER
        )
        ethnicity = StatePersonEthnicity.new_with_defaults(
            state_code=_STATE_CODE, ethnicity=StateEthnicity.NOT_HISPANIC
        )
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        external_id_2 = attr.evolve(entity_external_id_2, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id, external_id_2],
            races=[race],
            aliases=[alias],
            ethnicities=[ethnicity],
        )

        expected_race = attr.evolve(race)
        expected_ethnicity = attr.evolve(ethnicity)
        expected_alias = attr.evolve(alias)
        expected_person = attr.evolve(
            entity_person,
            external_ids=[
                entity_external_id,
                entity_external_id_2,
            ],
            races=[expected_race],
            ethnicities=[expected_ethnicity],
            aliases=[expected_alias],
            incarceration_sentences=[entity_incarceration_sentence],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person],
            matched_entities.root_entities,
            session,
        )

    def test_matchPersons_matchesTwoDbPeople_mergeAndMoveChildren(self) -> None:
        """Tests that our system correctly handles the situation where we have
        2 distinct people in our DB, but we learn the two DB people should be
        merged into 1 person based on a new ingested person. Here the two DB
        people to merge have children which match with each other, and therefore
        need to be merged properly themselves.
        """
        # Arrange 1 - Match
        db_person = generate_person(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_supervision_sentence = generate_supervision_sentence(
            person=db_person, external_id=_EXTERNAL_ID
        )
        entity_supervision_sentence = self.to_entity(
            db_supervision_sentence, StateSupervisionSentence
        )
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person.external_ids = [db_external_id]
        db_person.supervision_sentences = [db_supervision_sentence]
        entity_person = self.to_entity(db_person, StatePerson)

        db_person_dup = generate_person(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_supervision_period = generate_supervision_period(
            person=db_person_dup,
            external_id=_EXTERNAL_ID,
            start_date=_DATE_1,
            termination_date=_DATE_2,
        )
        entity_supervision_period = self.to_entity(
            db_supervision_period, StateSupervisionPeriod
        )
        db_supervision_sentence_dup = generate_supervision_sentence(
            person=db_person_dup,
            external_id=_EXTERNAL_ID_2,
            max_length_days=10,
        )
        entity_supervision_sentence_dup = self.to_entity(
            db_supervision_sentence_dup, StateSupervisionSentence
        )
        db_external_id_2 = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            id_type=_ID_TYPE_ANOTHER,
        )
        entity_external_id_2 = self.to_entity(db_external_id_2, StatePersonExternalId)
        db_person_dup.external_ids = [db_external_id_2]
        db_person_dup.supervision_sentences = [db_supervision_sentence_dup]
        db_person_dup.supervision_periods = [db_supervision_period]

        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        external_id_2 = attr.evolve(entity_external_id_2, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id, external_id_2],
        )

        self._commit_to_db(db_person, db_person_dup)

        expected_supervision_period = attr.evolve(entity_supervision_period)
        expected_supervision_sentence = attr.evolve(
            entity_supervision_sentence,
        )
        expected_supervision_sentence_dup = attr.evolve(entity_supervision_sentence_dup)
        expected_person = attr.evolve(
            entity_person,
            external_ids=[
                entity_external_id,
                entity_external_id_2,
            ],
            supervision_sentences=[
                expected_supervision_sentence,
                expected_supervision_sentence_dup,
            ],
            supervision_periods=[expected_supervision_period],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])
        self.maxDiff = None
        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person],
            matched_entities.root_entities,
            session,
        )

    def test_matchPersons_noPlaceholders_newPerson(self) -> None:
        # Arrange 1 - Match
        alias = StatePersonAlias.new_with_defaults(
            state_code=_STATE_CODE, full_name=_FULL_NAME
        )
        external_id = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, id_type=_ID_TYPE, external_id=_EXTERNAL_ID
        )
        race = StatePersonRace.new_with_defaults(
            state_code=_STATE_CODE, race=StateRace.WHITE
        )
        ethnicity = StatePersonEthnicity.new_with_defaults(
            state_code=_STATE_CODE, ethnicity=StateEthnicity.NOT_HISPANIC
        )
        person = StatePerson.new_with_defaults(
            gender=StateGender.MALE,
            aliases=[alias],
            external_ids=[external_id],
            races=[race],
            ethnicities=[ethnicity],
            state_code=_STATE_CODE,
        )

        expected_person = attr.evolve(person)

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_matchPersons_noPlaceholders_updatePersonAttributes(self) -> None:
        # Arrange 1 - Match
        db_race = generate_race(state_code=_STATE_CODE, race=StateRace.WHITE.value)
        entity_race = self.to_entity(db_race, StatePersonRace)
        db_alias = generate_alias(state_code=_STATE_CODE, full_name=_FULL_NAME)
        entity_alias = self.to_entity(db_alias, StatePersonAlias)
        db_ethnicity = generate_ethnicity(
            state_code=_STATE_CODE,
            ethnicity=StateEthnicity.HISPANIC.value,
        )
        entity_ethnicity = self.to_entity(db_ethnicity, StatePersonEthnicity)
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person = generate_person(
            full_name=_FULL_NAME,
            external_ids=[db_external_id],
            races=[db_race],
            aliases=[db_alias],
            ethnicities=[db_ethnicity],
            state_code=_STATE_CODE,
        )
        entity_person = self.to_entity(db_person, StatePerson)
        self._commit_to_db(db_person)

        race = StatePersonRace.new_with_defaults(
            state_code=_STATE_CODE, race=StateRace.BLACK
        )
        alias = StatePersonAlias.new_with_defaults(
            state_code=_STATE_CODE, full_name=_FULL_NAME_ANOTHER
        )
        ethnicity = StatePersonEthnicity.new_with_defaults(
            state_code=_STATE_CODE, ethnicity=StateEthnicity.NOT_HISPANIC
        )
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id],
            races=[race],
            aliases=[alias],
            ethnicities=[ethnicity],
        )

        expected_person = attr.evolve(
            entity_person,
            races=[entity_race, race],
            ethnicities=[entity_ethnicity, ethnicity],
            aliases=[entity_alias, alias],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_matchPersons_noPlaceholders_partialTreeIngested(self) -> None:
        # Arrange 1 - Match
        db_person = generate_person(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_charge_1 = generate_charge(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            description="charge_1",
            status=StateChargeStatus.PRESENT_WITHOUT_INFO.value,
        )
        entity_charge_1 = self.to_entity(db_charge_1, StateCharge)
        db_charge_2 = generate_charge(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            description="charge_2",
            status=StateChargeStatus.PRESENT_WITHOUT_INFO.value,
        )
        entity_charge_2 = self.to_entity(db_charge_2, StateCharge)
        db_supervision_sentence = generate_supervision_sentence(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            county_code="county_code",
            charges=[db_charge_1, db_charge_2],
        )
        entity_supervision_sentence = self.to_entity(
            db_supervision_sentence, StateSupervisionSentence
        )
        db_incarceration_sentence = generate_incarceration_sentence(
            person=db_person,
            status=StateSentenceStatus.SERVING.value,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            county_code="county_code",
        )
        entity_incarceration_sentence = self.to_entity(
            db_incarceration_sentence, StateIncarcerationSentence
        )
        db_external_id = generate_person_external_id(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person.external_ids = [db_external_id]
        db_person.supervision_sentences = [db_supervision_sentence]
        db_person.incarceration_sentences = [db_incarceration_sentence]
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        charge_1 = attr.evolve(
            entity_charge_1,
            charge_id=None,
            description="charge_1-updated",
        )
        charge_2 = attr.evolve(
            entity_charge_2,
            charge_id=None,
            description="charge_2-updated",
        )
        supervision_sentence = attr.evolve(
            entity_supervision_sentence,
            supervision_sentence_id=None,
            county_code="county-updated",
            charges=[charge_1, charge_2],
        )
        external_id = attr.evolve(
            entity_external_id, person_external_id_id=None, id_type=_ID_TYPE
        )
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id],
            supervision_sentences=[supervision_sentence],
        )

        expected_charge1 = attr.evolve(charge_1)
        expected_charge2 = attr.evolve(charge_2)
        expected_supervision_sentence = attr.evolve(
            supervision_sentence,
            charges=[expected_charge1, expected_charge2],
        )
        expected_unchanged_incarceration_sentence = attr.evolve(
            entity_incarceration_sentence
        )
        expected_external_id = attr.evolve(
            external_id,
        )
        expected_person = attr.evolve(
            person,
            external_ids=[expected_external_id],
            supervision_sentences=[expected_supervision_sentence],
            incarceration_sentences=[expected_unchanged_incarceration_sentence],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_matchPersons_noPlaceholders_completeTreeUpdate(self) -> None:
        # Arrange 1 - Match
        db_person = generate_person(full_name=_FULL_NAME, state_code=_STATE_CODE)
        db_charge_1 = generate_charge(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            description="charge_1",
            status=StateChargeStatus.PRESENT_WITHOUT_INFO.value,
        )
        entity_charge_1 = self.to_entity(db_charge_1, StateCharge)
        db_charge_2 = generate_charge(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_3,
            description="charge_2",
            status=StateChargeStatus.PRESENT_WITHOUT_INFO.value,
        )
        entity_charge_2 = self.to_entity(db_charge_2, StateCharge)
        db_assessment = generate_assessment(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            assessment_metadata="metadata",
        )
        entity_assessment = self.to_entity(db_assessment, StateAssessment)
        db_assessment_2 = generate_assessment(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID_2,
            assessment_metadata="metadata_2",
        )
        entity_assessment_2 = self.to_entity(db_assessment_2, StateAssessment)
        db_incarceration_incident = generate_incarceration_incident(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            incident_details="details",
        )
        entity_incarceration_incident = self.to_entity(
            db_incarceration_incident, StateIncarcerationIncident
        )
        db_supervision_violation_response_decision = (
            generate_supervision_violation_response_decision_entry(
                person=db_person,
                decision=StateSupervisionViolationResponseDecision.REVOCATION.value,
            )
        )
        entity_supervision_violation_response_decision = self.to_entity(
            db_supervision_violation_response_decision,
            StateSupervisionViolationResponseDecisionEntry,
        )
        db_supervision_violation_response = generate_supervision_violation_response(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            supervision_violation_response_decisions=[
                db_supervision_violation_response_decision
            ],
        )
        entity_supervision_violation_response = self.to_entity(
            db_supervision_violation_response, StateSupervisionViolationResponse
        )
        db_supervision_violation_type = generate_supervision_violation_type_entry(
            person=db_person,
            violation_type=StateSupervisionViolationType.ABSCONDED.value,
        )
        entity_supervision_violation_type = self.to_entity(
            db_supervision_violation_type, StateSupervisionViolationTypeEntry
        )
        db_supervision_violated_condition = generate_supervision_violated_condition_entry(
            person=db_person,
            condition=StateSupervisionViolatedConditionType.SPECIAL_CONDITIONS.value,
            condition_raw_text="COND",
        )
        entity_supervision_violated_condition = self.to_entity(
            db_supervision_violated_condition, StateSupervisionViolatedConditionEntry
        )
        db_supervision_violation = generate_supervision_violation(
            person=db_person,
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            is_violent=True,
            supervision_violation_types=[db_supervision_violation_type],
            supervision_violated_conditions=[db_supervision_violated_condition],
            supervision_violation_responses=[db_supervision_violation_response],
        )
        entity_supervision_violation = self.to_entity(
            db_supervision_violation, StateSupervisionViolation
        )
        db_incarceration_period = generate_incarceration_period(
            person=db_person,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            facility="facility",
        )
        entity_incarceration_period = self.to_entity(
            db_incarceration_period, StateIncarcerationPeriod
        )
        db_incarceration_sentence = generate_incarceration_sentence(
            person=db_person,
            status=StateSentenceStatus.SERVING.value,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            county_code="county_code",
            charges=[db_charge_1, db_charge_2],
        )
        entity_incarceration_sentence = self.to_entity(
            db_incarceration_sentence, StateIncarcerationSentence
        )
        db_case_type_dv = generate_supervision_case_type_entry(
            person=db_person,
            state_code=_STATE_CODE,
            case_type=StateSupervisionCaseType.DOMESTIC_VIOLENCE.value,
            case_type_raw_text="DV",
        )
        entity_case_type_dv = self.to_entity(
            db_case_type_dv, StateSupervisionCaseTypeEntry
        )
        db_supervision_period = generate_supervision_period(
            person=db_person,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            county_code="county_code",
            case_type_entries=[db_case_type_dv],
            supervising_officer_staff_external_id=_EXTERNAL_ID_5,
            supervising_officer_staff_external_id_type="EXTERNAL_ID_TYPE",
        )
        entity_supervision_period = self.to_entity(
            db_supervision_period, StateSupervisionPeriod
        )
        db_supervision_sentence = generate_supervision_sentence(
            person=db_person,
            status=StateSentenceStatus.SERVING.value,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            min_length_days=0,
        )
        entity_supervision_sentence = self.to_entity(
            db_supervision_sentence, StateSupervisionSentence
        )
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person.external_ids = [db_external_id]
        db_person.supervision_sentences = [db_supervision_sentence]
        db_person.incarceration_sentences = [db_incarceration_sentence]
        db_person.incarceration_periods = [db_incarceration_period]
        db_person.supervision_periods = [db_supervision_period]
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        charge_1 = attr.evolve(
            entity_charge_1,
            charge_id=None,
            description="charge_1-updated",
        )
        charge_2 = attr.evolve(
            entity_charge_2, charge_id=None, description="charge_2-updated"
        )
        assessment = attr.evolve(
            entity_assessment,
            assessment_id=None,
            assessment_metadata="metadata_updated",
        )
        assessment_2 = attr.evolve(
            entity_assessment_2,
            assessment_id=None,
            assessment_metadata="metadata_2-updated",
        )
        incarceration_incident = attr.evolve(
            entity_incarceration_incident,
            incarceration_incident_id=None,
            incident_details="details-updated",
        )
        incarceration_period = attr.evolve(
            entity_incarceration_period,
            incarceration_period_id=None,
            facility="facility-updated",
        )
        incarceration_sentence = attr.evolve(
            entity_incarceration_sentence,
            incarceration_sentence_id=None,
            county_code="county_code-updated",
            charges=[charge_1, charge_2],
        )
        supervision_violation_response_decision = attr.evolve(
            entity_supervision_violation_response_decision,
            supervision_violation_response_decision_entry_id=None,
        )
        supervision_violation_response = attr.evolve(
            entity_supervision_violation_response,
            supervision_violation_response_id=None,
            supervision_violation_response_decisions=[
                supervision_violation_response_decision
            ],
        )
        supervision_violation_type = attr.evolve(
            entity_supervision_violation_type,
            supervision_violation_type_entry_id=None,
        )
        supervision_violated_condition = attr.evolve(
            entity_supervision_violated_condition,
            supervision_violated_condition_entry_id=None,
        )
        supervision_violation = attr.evolve(
            entity_supervision_violation,
            supervision_violation_id=None,
            is_violent=False,
            supervision_violation_responses=[supervision_violation_response],
            supervision_violated_conditions=[supervision_violated_condition],
            supervision_violation_types=[supervision_violation_type],
        )
        case_type_dv = attr.evolve(
            entity_case_type_dv, supervision_case_type_entry_id=None
        )
        case_type_so = StateSupervisionCaseTypeEntry.new_with_defaults(
            state_code=_STATE_CODE,
            case_type=StateSupervisionCaseType.SEX_OFFENSE,
            case_type_raw_text="SO",
        )
        supervision_period = attr.evolve(
            entity_supervision_period,
            supervision_period_id=None,
            county_code="county_code-updated",
            case_type_entries=[case_type_dv, case_type_so],
            supervising_officer_staff_external_id=_EXTERNAL_ID_5,
            supervising_officer_staff_external_id_type="EXTERNAL_ID_TYPE",
        )
        supervision_sentence = attr.evolve(
            entity_supervision_sentence,
            supervision_sentence_id=None,
            min_length_days=1,
        )
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id],
            assessments=[assessment, assessment_2],
            incarceration_incidents=[incarceration_incident],
            supervision_violations=[supervision_violation],
            supervision_sentences=[supervision_sentence],
            incarceration_sentences=[incarceration_sentence],
            incarceration_periods=[incarceration_period],
            supervision_periods=[supervision_period],
        )

        expected_charge_1 = attr.evolve(
            charge_1,
        )
        expected_charge_2 = attr.evolve(charge_2)
        expected_assessment = attr.evolve(assessment)
        expected_assessment_2 = attr.evolve(assessment_2)
        expected_incarceration_incident = attr.evolve(
            incarceration_incident,
        )
        expected_incarceration_period = attr.evolve(
            incarceration_period,
        )
        expected_incarceration_sentence = attr.evolve(
            incarceration_sentence,
            charges=[expected_charge_1, expected_charge_2],
        )
        expected_supervision_violation_response_decision = attr.evolve(
            supervision_violation_response_decision,
        )
        expected_supervision_violation_response = attr.evolve(
            supervision_violation_response,
            supervision_violation_response_decisions=[
                expected_supervision_violation_response_decision
            ],
        )
        expected_supervision_violation_type = attr.evolve(supervision_violation_type)
        expected_supervision_violated_condition = attr.evolve(
            supervision_violated_condition
        )
        expected_supervision_violation = attr.evolve(
            supervision_violation,
            supervision_violation_responses=[expected_supervision_violation_response],
            supervision_violated_conditions=[expected_supervision_violated_condition],
            supervision_violation_types=[expected_supervision_violation_type],
        )
        expected_case_type_dv = attr.evolve(case_type_dv)
        expected_case_type_so = attr.evolve(case_type_so)
        expected_supervision_period = attr.evolve(
            supervision_period,
            case_type_entries=[expected_case_type_dv, expected_case_type_so],
        )
        expected_supervision_sentence = attr.evolve(
            supervision_sentence,
        )
        expected_external_id = attr.evolve(
            external_id,
        )
        expected_person = attr.evolve(
            person,
            external_ids=[expected_external_id],
            assessments=[expected_assessment, expected_assessment_2],
            incarceration_incidents=[expected_incarceration_incident],
            supervision_violations=[expected_supervision_violation],
            supervision_sentences=[expected_supervision_sentence],
            incarceration_sentences=[expected_incarceration_sentence],
            incarceration_periods=[expected_incarceration_period],
            supervision_periods=[expected_supervision_period],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_matchPersons_ingestedPersonWithNewExternalId(self) -> None:
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person = generate_person(
            full_name=_FULL_NAME,
            external_ids=[db_external_id],
            state_code=_STATE_CODE,
        )
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        external_id_another = StatePersonExternalId.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE_ANOTHER
        )
        person = StatePerson.new_with_defaults(
            external_ids=[external_id, external_id_another], state_code=_STATE_CODE
        )

        expected_external_id = attr.evolve(
            external_id,
        )
        expected_external_id_another = attr.evolve(external_id_another)
        expected_person = attr.evolve(
            entity_person,
            external_ids=[expected_external_id, expected_external_id_another],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_matchPersons_ingestedPersonPlaceholder_throws(self) -> None:
        sentence_new = StateSupervisionSentence.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
        )

        placeholder_person = StatePerson.new_with_defaults(
            supervision_sentences=[sentence_new],
            state_code=_STATE_CODE,
        )

        session = self._session()
        with self.assertRaisesRegex(
            ValueError,
            "Ingested root entity objects must have one or more assigned external ids.",
        ):
            _ = self._match(session, ingested_root_entities=[placeholder_person])

    def test_matchPersons_matchAfterManyIngestedPlaceholders(self) -> None:
        # Arrange 1 - Match
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            id_type=_ID_TYPE,
            external_id=_EXTERNAL_ID,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person = generate_person(
            external_ids=[db_external_id],
            state_code=_STATE_CODE,
        )
        db_incarceration_sentence = generate_incarceration_sentence(
            person=db_person, external_id=_EXTERNAL_ID
        )
        db_person.incarceration_sentences = [db_incarceration_sentence]
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        incarceration_incident = StateIncarcerationIncident.new_with_defaults(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID
        )
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = StatePerson.new_with_defaults(
            incarceration_incidents=[incarceration_incident],
            external_ids=[external_id],
            state_code=_STATE_CODE,
        )

        expected_incarceration_incident = attr.evolve(incarceration_incident)

        expected_external_id = attr.evolve(entity_external_id)
        expected_person = attr.evolve(
            entity_person,
            external_ids=[expected_external_id],
            incarceration_incidents=[expected_incarceration_incident],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_runMatch_multipleExternalIdsOnRootEntity(self) -> None:
        db_external_id = generate_person_external_id(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_external_id_2 = generate_person_external_id(
            external_id=_EXTERNAL_ID_2,
            state_code=_STATE_CODE,
            id_type=_ID_TYPE_ANOTHER,
        )
        entity_external_id_2 = self.to_entity(db_external_id_2, StatePersonExternalId)
        db_person = generate_person(
            external_ids=[db_external_id, db_external_id_2],
            state_code=_STATE_CODE,
        )
        entity_person = self.to_entity(db_person, StatePerson)
        self._commit_to_db(db_person)

        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        external_id_2 = attr.evolve(entity_external_id_2, person_external_id_id=None)
        race = StatePersonRace.new_with_defaults(
            race=StateRace.WHITE, state_code=_STATE_CODE
        )
        person = StatePerson.new_with_defaults(
            external_ids=[external_id, external_id_2],
            races=[race],
            state_code=_STATE_CODE,
        )

        expected_race = attr.evolve(race)
        expected_person = attr.evolve(entity_person, races=[expected_race])

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_mergeMultiParentEntities(self) -> None:
        # Arrange 1 - Match
        charge_merged = StateCharge.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateChargeStatus.PRESENT_WITHOUT_INFO,
        )
        charge_unmerged = attr.evolve(charge_merged, charge_id=None)
        charge_duplicate_unmerged = attr.evolve(charge_unmerged)
        sentence = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_unmerged],
        )
        sentence_2 = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID_2,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_duplicate_unmerged],
        )
        sentence_3 = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID_3,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_merged],
        )
        external_id = StatePersonExternalId.new_with_defaults(
            external_id=_EXTERNAL_ID, state_code=_STATE_CODE, id_type=_ID_TYPE
        )
        person = StatePerson.new_with_defaults(
            external_ids=[external_id],
            incarceration_sentences=[sentence, sentence_2, sentence_3],
            state_code=_STATE_CODE,
        )

        expected_charge = attr.evolve(charge_merged)
        expected_sentence = attr.evolve(sentence, charges=[expected_charge])
        expected_sentence_2 = attr.evolve(sentence_2, charges=[expected_charge])
        expected_sentence_3 = attr.evolve(sentence_3, charges=[expected_charge])
        expected_external_id = attr.evolve(external_id)
        expected_person = attr.evolve(
            person,
            external_ids=[expected_external_id],
            incarceration_sentences=[
                expected_sentence,
                expected_sentence_2,
                expected_sentence_3,
            ],
        )

        # Arrange 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person])

        # Assert 1 - Match
        found_person = matched_entities.root_entities[0]
        found_charge = found_person.incarceration_sentences[0].charges[0]
        found_charge_2 = found_person.incarceration_sentences[1].charges[0]
        found_charge_3 = found_person.incarceration_sentences[2].charges[0]
        self.assertEqual(id(found_charge), id(found_charge_2), id(found_charge_3))
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )

    def test_mergeMultiParentEntities_mergeCharges_errorInMerge_keepsOne(self) -> None:
        # Arrange 1 - Match
        charge = StateCharge.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateChargeStatus.PRESENT_WITHOUT_INFO,
        )
        charge_matching = attr.evolve(charge)
        sentence = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_matching],
        )
        sentence_2 = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID_2,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge],
        )
        external_id = StatePersonExternalId.new_with_defaults(
            external_id=_EXTERNAL_ID, state_code=_STATE_CODE, id_type=_ID_TYPE
        )
        person = StatePerson.new_with_defaults(
            external_ids=[external_id],
            incarceration_sentences=[sentence, sentence_2],
            state_code=_STATE_CODE,
        )

        expected_charge = attr.evolve(charge)
        expected_sentence = attr.evolve(sentence, charges=[expected_charge])
        expected_sentence_2 = attr.evolve(sentence_2, charges=[expected_charge])
        expected_external_id = attr.evolve(external_id)
        expected_person = attr.evolve(
            person,
            external_ids=[expected_external_id],
            incarceration_sentences=[expected_sentence, expected_sentence_2],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )

    def get_mismatched_tree_shape_input_and_expected(
        self,
    ) -> Tuple[List[StatePerson], List[StatePerson]]:
        """Returns a tuple of input_people, expected_matched_people where the input
        people have mismatched tree shapes.
        """
        charge_merged = StateCharge.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateChargeStatus.PRESENT_WITHOUT_INFO,
        )
        charge_unmerged = attr.evolve(charge_merged, charge_id=None)
        charge_duplicate_unmerged = attr.evolve(charge_unmerged)
        sentence = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_unmerged],
        )
        sentence_2 = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID_2,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_duplicate_unmerged],
        )
        sentence_3 = StateIncarcerationSentence.new_with_defaults(
            external_id=_EXTERNAL_ID_3,
            state_code=_STATE_CODE,
            status=StateSentenceStatus.PRESENT_WITHOUT_INFO,
            charges=[charge_merged],
        )
        external_id = StatePersonExternalId.new_with_defaults(
            external_id=_EXTERNAL_ID, state_code=_STATE_CODE, id_type=_ID_TYPE
        )
        person = StatePerson.new_with_defaults(
            external_ids=[external_id],
            incarceration_sentences=[sentence, sentence_2, sentence_3],
            state_code=_STATE_CODE,
        )

        other_person = StatePerson.new_with_defaults(
            state_code=_STATE_CODE,
            external_ids=[
                StatePersonExternalId.new_with_defaults(
                    state_code=_STATE_CODE, external_id=_EXTERNAL_ID_2, id_type=_ID_TYPE
                )
            ],
        )

        expected_charge = attr.evolve(charge_merged)
        expected_sentence = attr.evolve(sentence, charges=[expected_charge])
        expected_sentence_2 = attr.evolve(sentence_2, charges=[expected_charge])
        expected_sentence_3 = attr.evolve(sentence_3, charges=[expected_charge])
        expected_external_id = attr.evolve(external_id)
        expected_person = attr.evolve(
            person,
            external_ids=[expected_external_id],
            incarceration_sentences=[
                expected_sentence,
                expected_sentence_2,
                expected_sentence_3,
            ],
        )
        expected_other_person = attr.evolve(other_person)

        return [other_person, person], [expected_other_person, expected_person]

    def test_mergeMultiParentEntitiesMismatchedTreeShape(self) -> None:
        # Arrange 1 - Match
        (
            input_people,
            expected_people,
        ) = self.get_mismatched_tree_shape_input_and_expected()

        # Arrange 1 - Match
        session = self._session()
        matched_entities = self._match(session, input_people)

        # Assert 1 - Match
        found_person = one(
            p
            for p in matched_entities.root_entities
            if p.external_ids[0].external_id == _EXTERNAL_ID
        )
        found_charge = found_person.incarceration_sentences[0].charges[0]
        found_charge_2 = found_person.incarceration_sentences[1].charges[0]
        found_charge_3 = found_person.incarceration_sentences[2].charges[0]
        self.assertEqual(id(found_charge), id(found_charge_2), id(found_charge_3))
        self.assert_root_entities_match_pre_and_post_commit(
            expected_people,
            matched_entities.root_entities,
            session,
        )

    @patch(
        f"{state_entity_matcher.__name__}.NUM_TREES_TO_SEARCH_FOR_NON_PLACEHOLDER_TYPES",
        1,
    )
    @unittest.skip(
        "TODO(#7908): Re-enable once we go back to throwing errors on mismatched shapes"
    )
    def test_mergeMultiParentEntitiesMismatchedTreeShapeSmallerSearch(self) -> None:
        # Arrange 1 - Match
        (
            input_people,
            _,
        ) = self.get_mismatched_tree_shape_input_and_expected()

        # Arrange 1 - Match
        session = self._session()
        with self.assertRaisesRegex(
            ValueError,
            "^Failed to identify one of the non-placeholder ingest types: "
            r"\[StateSentenceGroup\]\.",
        ):
            _ = self._match(session, input_people)

    @patch(
        f"{state_entity_matcher.__name__}.MAX_NUM_TREES_TO_SEARCH_FOR_NON_PLACEHOLDER_TYPES",
        1,
    )
    def test_mismatchedTreeShapeEnumTypesOnly(self) -> None:
        # Arrange 1 - Match
        db_external_id = generate_person_external_id(
            external_id=_EXTERNAL_ID, id_type=_ID_TYPE
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_external_id_2 = generate_person_external_id(
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE_ANOTHER,
        )
        entity_external_id_2 = self.to_entity(db_external_id_2, StatePersonExternalId)
        db_person = generate_person(
            full_name=_FULL_NAME,
            external_ids=[db_external_id, db_external_id_2],
            state_code=_STATE_CODE,
        )
        entity_person = self.to_entity(db_person, StatePerson)
        self._commit_to_db(db_person)
        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id],
        )
        race = StatePersonRace.new_with_defaults(
            state_code=_STATE_CODE, race=StateRace.OTHER
        )
        external_id_2 = attr.evolve(entity_external_id_2, person_external_id_id=None)
        person_dup = attr.evolve(
            person, races=[race], external_ids=[attr.evolve(external_id_2)]
        )

        expected_external_id = attr.evolve(
            external_id,
        )
        expected_external_id_2 = attr.evolve(external_id_2)
        expected_race = attr.evolve(race)
        expected_person = attr.evolve(
            person,
            races=[expected_race],
            external_ids=[expected_external_id, expected_external_id_2],
        )

        # Arrange 1 - Match
        session = self._session()
        matched_entities = self._match(session, [person, person_dup])

        # Assert 1 - Match
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person],
            matched_entities.root_entities,
            session,
        )

    def test_mergeMultiParentEntityParentAndChild_multipleSentenceParents(self) -> None:
        """Tests merging multi-parent entities, but the two types of entities
        that must be merged are directly connected (themselves parent/child).
        In this tests case they are StateSupervisionViolation and
        StateSupervisionViolationResponse.
        """
        # Arrange
        db_person = generate_person(state_code=_STATE_CODE)
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE,
            external_id=_EXTERNAL_ID,
            id_type=_ID_TYPE,
        )
        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        db_person.external_ids = [db_external_id]
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        supervision_violation_response = (
            StateSupervisionViolationResponse.new_with_defaults(
                external_id=_EXTERNAL_ID, state_code=_STATE_CODE
            )
        )
        supervision_violation = StateSupervisionViolation.new_with_defaults(
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            supervision_violation_responses=[supervision_violation_response],
        )

        supervision_violation_response_dup = attr.evolve(supervision_violation_response)
        supervision_violation_dup = attr.evolve(
            supervision_violation,
            supervision_violation_responses=[supervision_violation_response_dup],
        )

        external_id = attr.evolve(entity_external_id, person_external_id_id=None)
        person = attr.evolve(
            entity_person,
            person_id=None,
            external_ids=[external_id],
            # These supervision violations should get merged
            supervision_violations=[supervision_violation, supervision_violation_dup],
        )

        # Only one expected violation response and violation, as they've been
        # merged
        expected_supervision_violation_response = attr.evolve(
            supervision_violation_response,
        )
        expected_supervision_violation = attr.evolve(
            supervision_violation,
            supervision_violation_responses=[expected_supervision_violation_response],
        )

        expected_person = attr.evolve(
            entity_person, supervision_violations=[expected_supervision_violation]
        )

        # Act
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assert_no_errors(matched_entities)
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_matchPersons_atomicIpMerge(self) -> None:
        # Arrange 1 - Match
        db_external_id = generate_person_external_id(
            state_code=_STATE_CODE, external_id=_EXTERNAL_ID
        )
        db_person = generate_person(
            full_name=_FULL_NAME,
            state_code=_STATE_CODE,
            external_ids=[db_external_id],
        )
        db_incarceration_period = generate_incarceration_period(
            db_person,
            external_id=_EXTERNAL_ID,
            state_code=_STATE_CODE,
            facility="facility",
            admission_date=datetime.date(2021, 4, 14),
            release_date=datetime.date(2022, 1, 1),
        )
        db_person.incarceration_periods = [db_incarceration_period]

        entity_external_id = self.to_entity(db_external_id, StatePersonExternalId)
        entity_incarceration_period = self.to_entity(
            db_incarceration_period, StateIncarcerationPeriod
        )
        entity_person = self.to_entity(db_person, StatePerson)

        self._commit_to_db(db_person)

        incarceration_period = attr.evolve(
            entity_incarceration_period,
            admission_date=datetime.date(2021, 5, 15),
            release_date=None,
        )
        external_id = attr.evolve(entity_external_id)
        person = attr.evolve(
            entity_person,
            external_ids=[external_id],
            incarceration_periods=[incarceration_period],
        )
        expected_incarceration_period = attr.evolve(incarceration_period)
        expected_external_id = attr.evolve(external_id)
        expected_person = attr.evolve(
            person,
            external_ids=[expected_external_id],
            incarceration_periods=[expected_incarceration_period],
        )

        # Act 1 - Match
        session = self._session()
        matched_entities = self._match(session, ingested_root_entities=[person])

        # Assert 1 - Match
        self.assert_no_errors(matched_entities)
        self.assert_root_entities_match_pre_and_post_commit(
            [expected_person], matched_entities.root_entities, session
        )
        self.assertEqual(1, matched_entities.total_root_entities)

    def test_get_non_placeholder_ingest_types_indices_to_search(self) -> None:
        for i in range(0, 2500 + 1):
            indices = (
                StateEntityMatcher.get_non_placeholder_ingest_types_indices_to_search(i)
            )
            if i < MAX_NUM_TREES_TO_SEARCH_FOR_NON_PLACEHOLDER_TYPES:
                self.assertEqual(i, len(indices))
            else:
                self.assertEqual(
                    MAX_NUM_TREES_TO_SEARCH_FOR_NON_PLACEHOLDER_TYPES, len(indices)
                )

            # Make sure all indices are in bounds
            self.assertFalse(any(index > i - 1 for index in indices))
