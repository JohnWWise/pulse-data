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
"""Utils for region controller tests."""
import datetime
from typing import List, Optional

from recidiviz.common.constants.state.state_assessment import (
    StateAssessmentClass,
    StateAssessmentLevel,
    StateAssessmentType,
)
from recidiviz.common.constants.state.state_drug_screen import (
    StateDrugScreenResult,
    StateDrugScreenSampleType,
)
from recidiviz.common.constants.state.state_employment_period import (
    StateEmploymentPeriodEmploymentStatus,
    StateEmploymentPeriodEndReason,
)
from recidiviz.common.constants.state.state_incarceration import StateIncarcerationType
from recidiviz.common.constants.state.state_incarceration_period import (
    StateIncarcerationPeriodAdmissionReason,
    StateIncarcerationPeriodCustodyLevel,
    StateIncarcerationPeriodHousingUnitCategory,
    StateIncarcerationPeriodHousingUnitType,
    StateIncarcerationPeriodReleaseReason,
    StateSpecializedPurposeForIncarceration,
)
from recidiviz.common.constants.state.state_sentence import StateSentenceStatus
from recidiviz.common.constants.state.state_shared_enums import StateCustodialAuthority
from recidiviz.common.constants.state.state_supervision_contact import (
    StateSupervisionContactLocation,
    StateSupervisionContactMethod,
    StateSupervisionContactReason,
    StateSupervisionContactStatus,
    StateSupervisionContactType,
)
from recidiviz.common.constants.state.state_supervision_period import (
    StateSupervisionLevel,
    StateSupervisionPeriodAdmissionReason,
    StateSupervisionPeriodSupervisionType,
    StateSupervisionPeriodTerminationReason,
)
from recidiviz.common.constants.state.state_supervision_sentence import (
    StateSupervisionSentenceSupervisionType,
)
from recidiviz.common.constants.states import StateCode
from recidiviz.persistence.entity.base_entity import Entity, RootEntity
from recidiviz.persistence.entity.entity_utils import (
    CoreEntityFieldIndex,
    get_all_entities_from_tree,
)
from recidiviz.persistence.entity.state import entities


def populate_root_entity_backedges(root_entities: List[RootEntity]) -> None:
    for root_entity in root_entities:
        back_edge_field_name = root_entity.back_edge_field_name()
        if not isinstance(root_entity, Entity):
            raise ValueError(
                f"Found RootEntity class [{type(root_entity)}] which is not a subclass of Entity"
            )
        children = get_all_entities_from_tree(root_entity, CoreEntityFieldIndex())
        for child in children:
            if (
                child is not root_entity
                and hasattr(child, back_edge_field_name)
                and getattr(child, back_edge_field_name, None) is None
            ):
                child.set_field(back_edge_field_name, root_entity)


# TODO(#21459) When writing parser tests, we'll end up creating many state people with
# only the external_id and state_code populated. There also is not a backedge on the
# StatePersonExternalId. We may wish to merge or clarify how to use these two functions.
def build_non_entity_matched_person(
    external_id: str, state_code: StateCode, unchecked_id_type: str
) -> entities.StatePerson:
    return entities.StatePerson(
        state_code=state_code.value,
        external_ids=[
            entities.StatePersonExternalId(
                state_code=state_code.value,
                external_id=external_id,
                id_type=unchecked_id_type,
            )
        ],
    )


def build_state_person_entity(
    state_code: str,
    id_type: str,
    full_name: Optional[str] = None,
    gender: Optional[entities.StateGender] = None,
    gender_raw_text: Optional[str] = None,
    birthdate: Optional[datetime.date] = None,
    external_id: Optional[str] = None,
    race_raw_text: Optional[str] = None,
    race: Optional[entities.StateRace] = None,
    ethnicity_raw_text: Optional[str] = None,
    ethnicity: Optional[entities.StateEthnicity] = None,
) -> entities.StatePerson:
    """Build a StatePerson entity with optional state_person_external_id, state_person_race
    and state_person_ethnicity entities appended"""
    state_person = entities.StatePerson.new_with_defaults(
        state_code=state_code,
        full_name=full_name,
        gender=gender,
        gender_raw_text=gender_raw_text,
        birthdate=birthdate,
    )
    if external_id:
        add_external_id_to_person(
            state_person,
            external_id=external_id,
            id_type=id_type,
            state_code=state_code,
        )
    if race and race_raw_text:
        add_race_to_person(
            state_person,
            race=race,
            race_raw_text=race_raw_text,
            state_code=state_code,
        )
    if ethnicity:
        add_ethnicity_to_person(
            state_person,
            ethnicity_raw_text=ethnicity_raw_text,
            ethnicity=ethnicity,
            state_code=state_code,
        )
    return state_person


def add_race_to_person(
    person: entities.StatePerson,
    race_raw_text: str,
    race: entities.StateRace,
    state_code: str,
) -> None:
    """Append race to the person (updates the person entity in place)."""
    race_to_add: entities.StatePersonRace = entities.StatePersonRace.new_with_defaults(
        state_code=state_code,
        race=race,
        race_raw_text=race_raw_text,
        person=person,
    )
    person.races.append(race_to_add)


def add_ethnicity_to_person(
    person: entities.StatePerson,
    ethnicity_raw_text: Optional[str],
    ethnicity: entities.StateEthnicity,
    state_code: str,
) -> None:
    """Append ethnicity to the person (updates the person entity in place)."""
    ethnicity_to_add: entities.StatePersonEthnicity = (
        entities.StatePersonEthnicity.new_with_defaults(
            state_code=state_code,
            ethnicity=ethnicity,
            ethnicity_raw_text=ethnicity_raw_text,
            person=person,
        )
    )
    person.ethnicities.append(ethnicity_to_add)


def add_external_id_to_person(
    person: entities.StatePerson, external_id: str, id_type: str, state_code: str
) -> None:
    """Append external id to the person (updates the person entity in place)."""
    external_id_to_add: entities.StatePersonExternalId = (
        entities.StatePersonExternalId.new_with_defaults(
            state_code=state_code,
            external_id=external_id,
            id_type=id_type,
            person=person,
        )
    )
    person.external_ids.append(external_id_to_add)


def add_alias_to_person(
    person: entities.StatePerson,
    state_code: str,
    full_name: str,
    alias_type: entities.StatePersonAliasType,
) -> None:
    """Append alias to the person (updates the person entity in place)."""
    alias_to_add: entities.StatePersonAlias = (
        entities.StatePersonAlias.new_with_defaults(
            state_code=state_code,
            person=person,
            full_name=full_name,
            alias_type=alias_type,
        )
    )
    person.aliases.append(alias_to_add)


def add_incarceration_period_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    admission_date: datetime.date,
    release_date: Optional[datetime.date],
    facility: str,
    housing_unit: Optional[str] = None,
    county_code: Optional[str] = None,
    custodial_authority: Optional[StateCustodialAuthority] = None,
    custodial_authority_raw_text: Optional[str] = None,
    admission_reason: Optional[StateIncarcerationPeriodAdmissionReason] = None,
    admission_reason_raw_text: Optional[str] = None,
    release_reason: Optional[StateIncarcerationPeriodReleaseReason] = None,
    release_reason_raw_text: Optional[str] = None,
    specialized_purpose_for_incarceration: Optional[
        StateSpecializedPurposeForIncarceration
    ] = None,
    incarceration_type: Optional[StateIncarcerationType] = None,
    incarceration_type_raw_text: Optional[str] = None,
    specialized_purpose_for_incarceration_raw_text: Optional[str] = None,
    custody_level: Optional[StateIncarcerationPeriodCustodyLevel] = None,
    custody_level_raw_text: Optional[str] = None,
    housing_unit_category: Optional[StateIncarcerationPeriodHousingUnitCategory] = None,
    housing_unit_category_raw_text: Optional[str] = None,
    housing_unit_type: Optional[StateIncarcerationPeriodHousingUnitType] = None,
    housing_unit_type_raw_text: Optional[str] = None,
) -> None:
    """Append an incarceration period to the person (updates the person entity in place)."""

    incarceration_period = entities.StateIncarcerationPeriod.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        admission_date=admission_date,
        release_date=release_date,
        county_code=county_code,
        facility=facility,
        housing_unit=housing_unit,
        custodial_authority=custodial_authority,
        custodial_authority_raw_text=custodial_authority_raw_text,
        admission_reason=admission_reason,
        admission_reason_raw_text=admission_reason_raw_text,
        release_reason=release_reason,
        release_reason_raw_text=release_reason_raw_text,
        person=person,
        incarceration_type=incarceration_type or StateIncarcerationType.STATE_PRISON,
        incarceration_type_raw_text=incarceration_type_raw_text,
        specialized_purpose_for_incarceration=specialized_purpose_for_incarceration,
        specialized_purpose_for_incarceration_raw_text=specialized_purpose_for_incarceration_raw_text,
        custody_level=custody_level,
        custody_level_raw_text=custody_level_raw_text,
        housing_unit_category=housing_unit_category,
        housing_unit_category_raw_text=housing_unit_category_raw_text,
        housing_unit_type=housing_unit_type,
        housing_unit_type_raw_text=housing_unit_type_raw_text,
    )

    person.incarceration_periods.append(incarceration_period)


def add_supervision_period_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    start_date: datetime.date,
    termination_date: Optional[datetime.date] = None,
    supervision_type: Optional[StateSupervisionPeriodSupervisionType] = None,
    supervision_type_raw_text: Optional[str] = None,
    supervision_site: Optional[str] = None,
    supervising_officer_staff_external_id: Optional[str] = None,
    supervising_officer_staff_external_id_type: Optional[str] = None,
    admission_reason: Optional[StateSupervisionPeriodAdmissionReason] = None,
    termination_reason: Optional[StateSupervisionPeriodTerminationReason] = None,
    conditions: Optional[str] = None,
    county_code: Optional[str] = None,
    admission_reason_raw_text: Optional[str] = None,
    termination_reason_raw_text: Optional[str] = None,
    custodial_authority_raw_text: Optional[str] = None,
    custodial_authority: Optional[StateCustodialAuthority] = None,
    supervision_level: Optional[StateSupervisionLevel] = None,
    supervision_level_raw_text: Optional[str] = None,
    case_type_entries: Optional[List[entities.StateSupervisionCaseTypeEntry]] = None,
) -> None:
    """Append a supervision period to the person (updates the person entity in place)."""

    supervision_period = entities.StateSupervisionPeriod.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        supervision_type=supervision_type,
        supervision_type_raw_text=supervision_type_raw_text,
        start_date=start_date,
        termination_date=termination_date,
        county_code=county_code,
        supervision_site=supervision_site,
        supervising_officer_staff_external_id=supervising_officer_staff_external_id,
        supervising_officer_staff_external_id_type=supervising_officer_staff_external_id_type,
        admission_reason=admission_reason,
        admission_reason_raw_text=admission_reason_raw_text,
        termination_reason=termination_reason,
        termination_reason_raw_text=termination_reason_raw_text,
        person=person,
        conditions=conditions,
        supervision_level=supervision_level,
        supervision_level_raw_text=supervision_level_raw_text,
        custodial_authority_raw_text=custodial_authority_raw_text,
        custodial_authority=custodial_authority,
        case_type_entries=case_type_entries or [],
    )

    if case_type_entries:
        for case_type_entry in case_type_entries:
            case_type_entry.supervision_period = supervision_period
            case_type_entry.person = person

    person.supervision_periods.append(supervision_period)


def add_assessment_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    assessment_class: Optional[StateAssessmentClass],
    assessment_type: Optional[StateAssessmentType],
    assessment_date: datetime.date,
    assessment_score: Optional[int],
    assessment_level: Optional[StateAssessmentLevel],
    assessment_level_raw_text: Optional[str],
    assessment_metadata: Optional[str],
    assessment_class_raw_text: Optional[str] = None,
    assessment_type_raw_text: Optional[str] = None,
    conducting_staff_external_id: Optional[str] = None,
    conducting_staff_external_id_type: Optional[str] = None,
) -> None:
    """Append an assessment to the person (updates the person entity in place)."""

    assessment = entities.StateAssessment.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        assessment_class=assessment_class,
        assessment_class_raw_text=assessment_class_raw_text,
        assessment_type=assessment_type,
        assessment_type_raw_text=assessment_type_raw_text,
        assessment_date=assessment_date,
        assessment_score=assessment_score,
        assessment_level=assessment_level,
        assessment_level_raw_text=assessment_level_raw_text,
        assessment_metadata=assessment_metadata,
        conducting_staff_external_id=conducting_staff_external_id,
        conducting_staff_external_id_type=conducting_staff_external_id_type,
        person=person,
    )

    person.assessments.append(assessment)


def add_supervision_sentence_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    status: StateSentenceStatus,
    status_raw_text: Optional[str],
    supervision_type: StateSupervisionSentenceSupervisionType,
    county_code: Optional[str] = None,
    supervision_type_raw_text: Optional[str] = None,
    date_imposed: Optional[datetime.date] = None,
    effective_date: Optional[datetime.date] = None,
    projected_completion_date: Optional[datetime.date] = None,
    completion_date: Optional[datetime.date] = None,
    is_life: Optional[bool] = None,
    min_length_days: Optional[int] = None,
    max_length_days: Optional[int] = None,
    sentence_metadata: Optional[str] = None,
    conditions: Optional[str] = None,
) -> entities.StateSupervisionSentence:
    """Append a supervision sentence to the person (updates the person entity in place)."""

    supervision_sentence = entities.StateSupervisionSentence.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        status=status,
        status_raw_text=status_raw_text,
        supervision_type=supervision_type,
        supervision_type_raw_text=supervision_type_raw_text,
        date_imposed=date_imposed,
        effective_date=effective_date,
        projected_completion_date=projected_completion_date,
        completion_date=completion_date,
        is_life=is_life,
        county_code=county_code,
        min_length_days=min_length_days,
        max_length_days=max_length_days,
        sentence_metadata=sentence_metadata,
        conditions=conditions,
        person=person,
    )

    person.supervision_sentences.append(supervision_sentence)
    return supervision_sentence


def add_incarceration_sentence_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    status: StateSentenceStatus,
    status_raw_text: Optional[str],
    incarceration_type: StateIncarcerationType,
    incarceration_type_raw_text: Optional[str],
    county_code: Optional[str],
    date_imposed: Optional[datetime.date] = None,
    effective_date: Optional[datetime.date] = None,
    projected_min_release_date: Optional[datetime.date] = None,
    projected_max_release_date: Optional[datetime.date] = None,
    completion_date: Optional[datetime.date] = None,
    earned_time_days: Optional[int] = None,
    good_time_days: Optional[int] = None,
    initial_time_served_days: Optional[int] = None,
    min_length_days: Optional[int] = None,
    max_length_days: Optional[int] = None,
    is_life: Optional[bool] = False,
    is_capital_punishment: Optional[bool] = False,
    parole_possible: Optional[bool] = False,
    sentence_metadata: Optional[str] = None,
    conditions: Optional[str] = None,
    parole_eligibility_date: Optional[datetime.date] = None,
) -> entities.StateIncarcerationSentence:
    """Append an incarceration sentence to the person (updates the person entity in place)."""

    incarceration_sentence = entities.StateIncarcerationSentence.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        status=status,
        status_raw_text=status_raw_text,
        incarceration_type=incarceration_type,
        incarceration_type_raw_text=incarceration_type_raw_text,
        date_imposed=date_imposed,
        effective_date=effective_date,
        projected_min_release_date=projected_min_release_date,
        projected_max_release_date=projected_max_release_date,
        completion_date=completion_date,
        county_code=county_code,
        min_length_days=min_length_days,
        max_length_days=max_length_days,
        is_life=is_life,
        is_capital_punishment=is_capital_punishment,
        parole_possible=parole_possible,
        earned_time_days=earned_time_days,
        good_time_days=good_time_days,
        initial_time_served_days=initial_time_served_days,
        sentence_metadata=sentence_metadata,
        conditions=conditions,
        parole_eligibility_date=parole_eligibility_date,
        person=person,
    )

    person.incarceration_sentences.append(incarceration_sentence)
    return incarceration_sentence


def add_supervision_contact_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    contact_date: Optional[datetime.date] = None,
    contact_reason: Optional[StateSupervisionContactReason] = None,
    contact_reason_raw_text: Optional[str] = None,
    contact_type: Optional[StateSupervisionContactType] = None,
    contact_type_raw_text: Optional[str] = None,
    contact_method: Optional[StateSupervisionContactMethod] = None,
    contact_method_raw_text: Optional[str] = None,
    location: Optional[StateSupervisionContactLocation] = None,
    location_raw_text: Optional[str] = None,
    resulted_in_arrest: Optional[bool] = None,
    status: Optional[StateSupervisionContactStatus] = None,
    status_raw_text: Optional[str] = None,
    verified_employment: Optional[bool] = None,
    supervision_contact_id: Optional[int] = None,
    contacting_staff_external_id: Optional[str] = None,
    contacting_staff_external_id_type: Optional[str] = None,
) -> entities.StateSupervisionContact:
    """Append a supervision contact to the person (updates the person entity in place)."""

    supervision_contact = entities.StateSupervisionContact.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        contact_date=contact_date,
        contact_reason=contact_reason,
        contact_reason_raw_text=contact_reason_raw_text,
        contact_type=contact_type,
        contact_type_raw_text=contact_type_raw_text,
        contact_method=contact_method,
        contact_method_raw_text=contact_method_raw_text,
        location=location,
        location_raw_text=location_raw_text,
        resulted_in_arrest=resulted_in_arrest,
        status=status,
        status_raw_text=status_raw_text,
        verified_employment=verified_employment,
        supervision_contact_id=supervision_contact_id,
        contacting_staff_external_id=contacting_staff_external_id,
        contacting_staff_external_id_type=contacting_staff_external_id_type,
        person=person,
    )

    person.supervision_contacts.append(supervision_contact)
    return supervision_contact


def add_drug_screen_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    drug_screen_date: datetime.date,
    drug_screen_result: Optional[StateDrugScreenResult],
    drug_screen_result_raw_text: Optional[str],
    sample_type: Optional[StateDrugScreenSampleType],
    sample_type_raw_text: Optional[str],
) -> None:
    """Append a drug screen to the person (updates the person entity in place)."""

    drug_screen = entities.StateDrugScreen.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        drug_screen_date=drug_screen_date,
        drug_screen_result=drug_screen_result,
        drug_screen_result_raw_text=drug_screen_result_raw_text,
        sample_type=sample_type,
        sample_type_raw_text=sample_type_raw_text,
        person=person,
    )

    person.drug_screens.append(drug_screen)


def add_employment_period_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    employment_status: Optional[StateEmploymentPeriodEmploymentStatus] = None,
    employment_status_raw_text: Optional[str] = None,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    last_verified_date: Optional[datetime.date] = None,
    employer_name: Optional[str] = None,
    employer_address: Optional[str] = None,
    job_title: Optional[str] = None,
    end_reason: Optional[StateEmploymentPeriodEndReason] = None,
    end_reason_raw_text: Optional[str] = None,
) -> None:
    """Append a drug screen to the person (updates the person entity in place)."""

    employment_period = entities.StateEmploymentPeriod.new_with_defaults(
        external_id=external_id,
        state_code=state_code,
        employment_status=employment_status,
        employment_status_raw_text=employment_status_raw_text,
        start_date=start_date,
        end_date=end_date,
        last_verified_date=last_verified_date,
        employer_name=employer_name,
        employer_address=employer_address,
        job_title=job_title,
        end_reason=end_reason,
        end_reason_raw_text=end_reason_raw_text,
        person=person,
    )

    person.employment_periods.append(employment_period)


def add_external_id_to_staff(
    staff: entities.StateStaff, external_id: str, id_type: str, state_code: str
) -> None:
    """Append external id to the person (updates the person entity in place)."""
    external_id_to_add: entities.StateStaffExternalId = (
        entities.StateStaffExternalId.new_with_defaults(
            state_code=state_code,
            external_id=external_id,
            id_type=id_type,
            staff=staff,
        )
    )
    staff.external_ids.append(external_id_to_add)


def add_supervisor_period_to_staff(
    staff: entities.StateStaff,
    external_id: str,
    supervisor_staff_external_id: str,
    supervisor_staff_external_id_type: str,
    start_date: datetime.date,
    end_date: Optional[datetime.date],
    state_code: str,
) -> None:
    """Append external id to the person (updates the person entity in place)."""
    supervisor_period_to_add: entities.StateStaffSupervisorPeriod = (
        entities.StateStaffSupervisorPeriod.new_with_defaults(
            state_code=state_code,
            external_id=external_id,
            supervisor_staff_external_id=supervisor_staff_external_id,
            supervisor_staff_external_id_type=supervisor_staff_external_id_type,
            start_date=start_date,
            end_date=end_date,
            staff=staff,
        )
    )
    staff.supervisor_periods.append(supervisor_period_to_add)


def add_supervision_violation_to_person(
    person: entities.StatePerson,
    state_code: str,
    external_id: str,
    ## EG Note: When these default to None instead of [], and the field has no values,
    ## the controller test throws an error because the type is None instead of a list.
    ## Shouldn't using Optional[] make None an acceptable type for these fields?
    supervision_violation_responses: Optional[
        List[entities.StateSupervisionViolationResponse]
    ] = None,
    supervision_violation_types: Optional[
        List[entities.StateSupervisionViolationTypeEntry]
    ] = None,
    supervision_violated_conditions: Optional[
        List[entities.StateSupervisionViolatedConditionEntry]
    ] = None,
    violation_date: Optional[datetime.date] = None,
    violation_metadata: Optional[str] = None,
) -> None:
    """Append a supervision violation to the person (updates the person entity in place)."""

    supervision_violation = entities.StateSupervisionViolation.new_with_defaults(
        state_code=state_code,
        external_id=external_id,
        supervision_violation_responses=supervision_violation_responses or [],
        supervision_violation_types=supervision_violation_types or [],
        supervision_violated_conditions=supervision_violated_conditions or [],
        violation_date=violation_date,
        violation_metadata=violation_metadata,
        person=person,
    )

    if supervision_violation_types:
        for supervision_violation_type in supervision_violation_types:
            supervision_violation_type.supervision_violation = supervision_violation
            supervision_violation_type.person = person

    if supervision_violated_conditions:
        for supervision_violated_condition in supervision_violated_conditions:
            supervision_violated_condition.supervision_violation = supervision_violation
            supervision_violated_condition.person = person

    if supervision_violation_responses:
        for supervision_violation_response in supervision_violation_responses:
            supervision_violation_response.supervision_violation = supervision_violation
            supervision_violation_response.person = person
            for (
                supervision_violation_response_decision
            ) in (
                supervision_violation_response.supervision_violation_response_decisions
            ):
                supervision_violation_response_decision.supervision_violation_response = (
                    supervision_violation_response
                )
                supervision_violation_response_decision.person = person

    person.supervision_violations.append(supervision_violation)
