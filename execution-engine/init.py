import logging
from typing import Any, OrderedDict

from config import RecommendationSet, Settings

settings = Settings()  # Settings for this script


def init_execution_engine():
    """
    Initializes the ExecutionEngine by adding customized converters.
    """
    from digipod.terminology.vocabulary import DigiPOD
    from execution_engine.builder import default_execution_engine_builder
    from execution_engine.omop.criterion.factory import register_criterion_class
    from execution_engine.omop.vocabulary import standard_vocabulary

    standard_vocabulary.register(DigiPOD)

    from digipod.converter.age import AgeConverter
    from digipod.converter.condition import DigiPODConditionCharacteristic
    from digipod.converter.evaluation_procedure import (
        AssessmentCharacteristicConverter,
        OtherActionConverter,
        ProcedureWithExplicitContextConverter,
    )
    from digipod.converter.time_from_event import SurgicalOperationDate
    from digipod.criterion.patients import AgeLimitPatient

    register_criterion_class("AgeLimitPatient", AgeLimitPatient)

    builder = default_execution_engine_builder()

    builder.prepend_characteristic_converter(AgeConverter)
    builder.prepend_characteristic_converter(AssessmentCharacteristicConverter)
    builder.prepend_characteristic_converter(ProcedureWithExplicitContextConverter)
    builder.prepend_characteristic_converter(DigiPODConditionCharacteristic)

    builder.prepend_action_converter(OtherActionConverter)

    builder.append_time_from_event_converter(SurgicalOperationDate)

    # Build the ExecutionEngine
    engine = builder.build()

    return engine


def load_recommendations_for_celida(
    engine: Any,  # The ExecutionEngine type is imported later
):
    """
    Load the configured recommendations, either by retrieving them
    from the recommendation server or by restoring the serialized
    representations from the database.
    """
    recommendation_package_version = "v1.5.2"

    base_url = (
        "https://www.netzwerk-universitaetsmedizin.de/fhir/codex-celida/guideline/"
    )

    urls = [
        "covid19-inpatient-therapy/recommendation/no-therapeutic-anticoagulation",
        "sepsis/recommendation/ventilation-plan-ards-tidal-volume",
        "covid19-inpatient-therapy/recommendation/ventilation-plan-ards-tidal-volume",
        "covid19-inpatient-therapy/recommendation/covid19-ventilation-plan-peep",
        "covid19-inpatient-therapy/recommendation/prophylactic-anticoagulation",
        "covid19-inpatient-therapy/recommendation/therapeutic-anticoagulation",
        "covid19-inpatient-therapy/recommendation/covid19-abdominal-positioning-ards",
    ]

    logging.info(
        f"Loading CELIDA recommendations with base URL {base_url}"
        f"and version {recommendation_package_version}"
    )
    recommendations = [
        engine.load_recommendation(
            base_url + recommendation_url,
            recommendation_package_version=recommendation_package_version,
        )
        for recommendation_url in urls
    ]
    logging.info(f"{len(recommendations)} recommendations loaded")
    return recommendations


# TODO(jmoringe): can we import the module earlier without triggering
# the schema creation?
def load_recommendations_for_digipod(
    engine: Any,  # The ExecutionEngine type is imported later
):
    """
    Load the (hardcoded) recommendations for DigiPOD from the digipod package.
    """
    logging.info("Loading DigiPOD recommendations")

    from digipod.terminology.vocabulary import DigiPOD
    from execution_engine.omop.vocabulary import standard_vocabulary

    standard_vocabulary.register(DigiPOD)

    import digipod.recommendation.recommendation_0_1 as r01
    import digipod.recommendation.recommendation_0_2 as r02
    import digipod.recommendation.recommendation_2_1 as r21
    import digipod.recommendation.recommendation_3_2 as r32

    recommendation_package_version = "latest"
    base_url = "https://fhir.charite.de/digipod/"

    urls: OrderedDict[str, str] = OrderedDict()
    # manually implemented
    # urls["0.1"] = "PlanDefinition/RecCollPreoperativeDeliriumScreening"
    # urls["0.2"] = "PlanDefinition/RecCollDeliriumScreeningPostoperatively"
    # urls["2.1"] = "PlanDefinition/RecCollCheckRFAdultSurgicalPatientsPreoperatively"
    # urls["3.1"] = "PlanDefinition/RecCollAdultSurgicalPatNoSpecProphylacticDrugForPOD"

    # priority
    # urls["4.1"] = "PlanDefinition/RecCollPreoperativeRFAssessmentAndOptimization"
    # urls["4.3."] = None
    # urls["4.2"] = "PlanDefinition/RecCollShareRFOfOlderAdultsPreOPAndRegisterPreventiveStrategies"

    # unknown
    # urls["3.2"] = "PlanDefinition/RecCollBalanceBenefitsAgainstSideEffectsWhenUsingDexmedetomidine"
    # urls["3.3"] = "PlanDefinition/RecCollAdultSurgicalPatPreOrIntraOPNoSpecSurgeryOrAnesthesiaType"
    # urls["3.4"] = "PlanDefinition/RecCollAdultSurgicalPatPreOrIntraOPNoSpecificBiomarker"
    # urls["5.1"] = "PlanDefinition/RecCollIntraoperativeEEGMonitoringDepth"
    # urls["5.2"] = "PlanDefinition/RecCollIntraoperativeMultiparameterEEG"
    # urls["6.2"] = "PlanDefinition/RecCollBenzoTreatmentofDeliriumInAdultSurgicalPatPostoperatively"
    # urls["6.3"] = "PlanDefinition/RecCollAdministerDexmedetomidineToPostOPCardiacSurgeryPatForPOD"

    recommendations = [
        r01.rec_0_1_Delirium_Screening,
        r02.rec_0_2_Delirium_Screening_single,
        r02.rec_0_2_Delirium_Screening_double,
        r21.RecCollCheckRFAdultSurgicalPatientsPreoperatively,
        r32.RecCollCheckRFAdultSurgicalPatientsPreoperatively,
    ]

    for rec_no, recommendation_url in urls.items():
        print(rec_no, recommendation_url)
        cdd = engine.load_recommendation(
            base_url + recommendation_url,
            recommendation_package_version=recommendation_package_version,
        )
        recommendations.append(cdd)

    for recommendation in recommendations:
        engine.register_recommendation(recommendation)

    logging.info(f"{len(recommendations)} recommendations loaded")

    return recommendations


def load_recommendations(engine: Any):
    """
    Load recommendations into engine, either CELIDA recommandetation
    from a recommendaion server or hardcoded DigiPOD recommendataions
    from the ee_addons package.
    """
    if settings.recommendation_set == RecommendationSet.celida:
        return load_recommendations_for_celida(engine)
    elif settings.recommendation_set == RecommendationSet.digipod:
        return load_recommendations_for_digipod(engine)
    else:
        assert False  # unreachable
