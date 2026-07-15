"""Coordinate fresh inspection, deterministic grading, and explain-back evaluation."""

from ownyourcode.modules.assessments.definition import (
    AssessmentDefinition,
    build_assessment_definition,
)
from ownyourcode.modules.assessments.openai_client import OpenAIAssessmentClient
from ownyourcode.modules.assessments.schemas import (
    AssessmentEvaluationRequest,
    AssessmentEvaluationResponse,
    AssessmentQuestionsRequest,
    AssessmentQuestionsResponse,
    DeterministicFeedback,
    EVIDENCE_SELECTION_QUESTION_ID,
    EvidenceSelectionQuestion,
    EXPLAIN_BACK_QUESTION_ID,
    ExplainBackFeedback,
    ExplainBackQuestion,
    MultipleChoiceQuestion,
    MULTIPLE_CHOICE_QUESTION_ID,
    AssessmentScore,
)
from ownyourcode.modules.lessons.evidence import build_evidence_catalog
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


class AssessmentContextStaleError(Exception):
    """The learner submitted answers for inspection evidence that has changed."""


class AssessmentAnswerError(Exception):
    """Submitted IDs are not members of the freshly built public question set."""


class ArchitectureOrientationAssessmentService:
    """All assessment results are previews; no questions or answers are stored."""

    def __init__(
        self,
        repository_inspection_service: PublicRepositoryInspectionService,
        openai_client: OpenAIAssessmentClient,
    ) -> None:
        self._repository_inspection_service = repository_inspection_service
        self._openai_client = openai_client

    def prepare_questions(
        self, request: AssessmentQuestionsRequest
    ) -> AssessmentQuestionsResponse:
        inspection = self._repository_inspection_service.inspect_url(request.repository_url)
        catalog = build_evidence_catalog(inspection)
        definition = build_assessment_definition(
            repository_url=request.repository_url,
            learner_level=request.learner_level,
            catalog=catalog,
        )
        return AssessmentQuestionsResponse(
            assessment_context_id=definition.context_id,
            inspection_limitations=inspection.limitations,
            questions=definition.questions,
        )

    def evaluate(self, request: AssessmentEvaluationRequest) -> AssessmentEvaluationResponse:
        # Avoid GitHub work if model configuration cannot possibly evaluate explain-back.
        self._openai_client.ensure_configured()
        inspection = self._repository_inspection_service.inspect_url(request.repository_url)
        catalog = build_evidence_catalog(inspection)
        definition = build_assessment_definition(
            repository_url=request.repository_url,
            learner_level=request.learner_level,
            catalog=catalog,
        )
        if request.assessment_context_id != definition.context_id:
            raise AssessmentContextStaleError()
        multiple_choice_question = _question(definition, MultipleChoiceQuestion)
        evidence_question = _question(definition, EvidenceSelectionQuestion)
        explain_question = _question(definition, ExplainBackQuestion)
        allowed_option_ids = {option.id for option in multiple_choice_question.options}
        allowed_evidence_ids = {choice.id for choice in explain_question.evidence_choices}
        if request.answers.multiple_choice.selected_option_id not in allowed_option_ids:
            raise AssessmentAnswerError()
        if request.answers.evidence_selection.selected_evidence_id not in {
            choice.id for choice in evidence_question.evidence_choices
        }:
            raise AssessmentAnswerError()
        if any(
            evidence_id not in allowed_evidence_ids
            for evidence_id in request.answers.explain_back.evidence_ids
        ):
            raise AssessmentAnswerError()

        multiple_correct = (
            request.answers.multiple_choice.selected_option_id
            == definition.multiple_choice_correct_option_id
        )
        evidence_correct = (
            request.answers.evidence_selection.selected_evidence_id
            == definition.evidence_selection_correct_id
        )
        selected_choices = [
            {"id": choice.id, "label": choice.label}
            for choice in explain_question.evidence_choices
            if choice.id in request.answers.explain_back.evidence_ids
        ]
        model_evaluation = self._openai_client.evaluate(
            learner_level=request.learner_level,
            target_label=definition.target_evidence.label,
            evidence_choices=selected_choices,
            inspection_limitations=inspection.limitations,
            learner_answer=request.answers.explain_back.answer_text,
        )
        deterministic_points = int(multiple_correct) + int(evidence_correct)
        return AssessmentEvaluationResponse(
            score=AssessmentScore(
                earned_points=deterministic_points + model_evaluation.earned_points
            ),
            feedback=[
                DeterministicFeedback(
                    question_id=MULTIPLE_CHOICE_QUESTION_ID,
                    earned_points=int(multiple_correct),
                    message=(
                        "Your selection matches a claim supported by the deterministic repository orientation."
                        if multiple_correct
                        else "That submitted claim is not supported by this bounded orientation. Revisit the inspection limitations and confirmed evidence."
                    ),
                ),
                DeterministicFeedback(
                    question_id=EVIDENCE_SELECTION_QUESTION_ID,
                    earned_points=int(evidence_correct),
                    message=(
                        "Your selected evidence directly supports the repository-orientation target."
                        if evidence_correct
                        else "That evidence does not directly support the repository-orientation target. Revisit the evidence labels."
                    ),
                ),
            ],
            explain_back_feedback=ExplainBackFeedback(
                question_id=EXPLAIN_BACK_QUESTION_ID,
                earned_points=model_evaluation.earned_points,
                feedback=model_evaluation.feedback,
            ),
            inspection_limitations=inspection.limitations,
        )


def _question(
    definition: AssessmentDefinition, question_type: type[object]
) -> object:
    return next(question for question in definition.questions if isinstance(question, question_type))
