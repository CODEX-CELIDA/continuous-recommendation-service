import inspect
import logging
from types import ModuleType
from typing import Any, Generator, OrderedDict, Type

from config import RecommendationSet, Settings

settings = Settings()  # Settings for this script


def iterate_module_classes(module: ModuleType) -> Generator[Type, None, None]:
    """
    Yields all classes listed in the `__all__` attribute of a module.

    :param module: The module from which to import classes.
    :return: A generator yielding classes defined in the module's `__all__` list.
    """

    if hasattr(module, "__all__"):
        for class_name in module.__all__:
            cls = getattr(module, class_name, None)
            if inspect.isclass(cls):
                yield cls


def init_execution_engine():
    """
    Initializes the ExecutionEngine by adding customized converters.
    """
    from digipod.terminology.vocabulary import DigiPOD
    from execution_engine.builder import default_execution_engine_builder
    from execution_engine.omop.vocabulary import standard_vocabulary

    standard_vocabulary.register(DigiPOD)

    import digipod.converter.action
    import digipod.converter.characteristic
    import digipod.converter.time_from_event
    import digipod.criterion

    builder = default_execution_engine_builder()

    for cls in iterate_module_classes(digipod.converter.characteristic):
        logging.info(f'Importing characteristic converter "{cls.__name__}"')
        builder.prepend_characteristic_converter(cls)

    for cls in iterate_module_classes(digipod.converter.action):
        logging.info(f'Importing action converter "{cls.__name__}"')
        builder.prepend_action_converter(cls)

    for cls in iterate_module_classes(digipod.converter.time_from_event):
        logging.info(f'Importing timeFromEvent converter "{cls.__name__}"')
        builder.append_time_from_event_converter(cls)

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
    import digipod.recommendation.recommendation_4_1 as r41
    import digipod.recommendation.recommendation_4_2 as r42
    import digipod.recommendation.recommendation_4_3 as r43

    recommendation_package_version = "latest"
    base_url = "https://fhir.charite.de/digipod/"

    urls: OrderedDict[str, str] = OrderedDict()
    # manually implemented
    # urls["0.1"] = "PlanDefinition/RecCollPreoperativeDeliriumScreening"
    # urls["0.2"] = "PlanDefinition/RecCollDeliriumScreeningPostoperatively"
    # urls["2.1"] = "PlanDefinition/RecCollCheckRFAdultSurgicalPatientsPreoperatively"
    # urls["3.2"] = "PlanDefinition/RecCollProphylacticDexAdministrationAfterBalancingBenefitsVSSE"

    # priority
    # urls["4.1"] = "PlanDefinition/RecCollPreoperativeRFAssessmentAndOptimization"
    # urls["4.2"] = "PlanDefinition/RecCollShareRFOfOlderAdultsPreOPAndRegisterPreventiveStrategies"
    # urls["4.3"] = "PlanDefinition/RecCollBundleOfNonPharmaMeasuresPostOPInAdultsAtRiskForPOD"

    # unknown
    # urls["3.1"] = "PlanDefinition/RecCollAdultSurgicalPatNoSpecProphylacticDrugForPOD"
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
        r32.recommendation,
        r41.recommendation,
        r42.recommendation,
        r43.recommendation,
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
    Load recommendations into engine, either CELIDA recommendation
    from a recommendation server or hardcoded DigiPOD recommendations
    from the ee_addons package.
    """
    if settings.recommendation_set == RecommendationSet.celida:
        return load_recommendations_for_celida(engine)
    elif settings.recommendation_set == RecommendationSet.digipod:
        return load_recommendations_for_digipod(engine)
    else:
        assert False  # unreachable
