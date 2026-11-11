"""
AI Question Generation Service
Integrates with OpenAI/Claude API for automated question generation
"""
import json
import logging
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.utils import timezone
import requests
from .models import Question, QuestionOption, QuestionBank, AIGenerationLog

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """
    Service for generating questions using AI APIs
    """

    def __init__(self, api_key: str = None, provider: str = 'openai'):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.provider = provider
        self.base_url = self._get_base_url()

    def _get_base_url(self) -> str:
        """Get API base URL based on provider"""
        if self.provider.lower() == 'openai':
            return 'https://api.openai.com/v1'
        elif self.provider.lower() == 'claude':
            return 'https://api.anthropic.com/v1'
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def generate_questions(
        self,
        topic: str,
        question_bank: QuestionBank,
        count: int = 5,
        difficulty: str = 'medium',
        question_types: List[str] = None
    ) -> Tuple[List[Dict], str]:
        """
        Generate questions using AI

        Args:
            topic: Topic for question generation
            question_bank: QuestionBank instance to associate questions with
            count: Number of questions to generate
            difficulty: Difficulty level (easy, medium, hard, expert)
            question_types: List of question types to generate

        Returns:
            Tuple of (questions_data, model_used)
        """
        if not question_types:
            question_types = ['multiple_choice', 'true_false']

        # Build prompt
        prompt = self._build_generation_prompt(topic, count, difficulty, question_types)

        try:
            response = self._call_ai_api(prompt)
            questions_data = self._parse_ai_response(response)

            # Validate and clean the generated questions
            validated_questions = []
            for q_data in questions_data:
                if self._validate_question_data(q_data):
                    validated_questions.append(q_data)

            return validated_questions, self._get_model_name()

        except Exception as e:
            logger.error(f"AI question generation failed: {str(e)}")
            raise

    def _build_generation_prompt(
        self,
        topic: str,
        count: int,
        difficulty: str,
        question_types: List[str]
    ) -> str:
        """Build the AI prompt for question generation"""
        type_instructions = {
            'multiple_choice': """
            - Multiple Choice: Create questions with 4 options, exactly one correct answer
            - Format: Question text, then list 4 options (A, B, C, D), then specify the correct answer
            """,
            'true_false': """
            - True/False: Create statements that are clearly true or false
            - Format: Statement, then specify if true or false
            """,
            'short_answer': """
            - Short Answer: Questions requiring 1-2 sentence answers
            - Format: Question text, then provide the expected answer
            """
        }

        selected_instructions = "\n".join([
            type_instructions.get(qt, "") for qt in question_types
        ])

        prompt = f"""
        Generate {count} educational questions about: {topic}

        Difficulty Level: {difficulty}

        Question Types to Generate:
        {selected_instructions}

        Requirements:
        - Questions should be appropriate for {question_bank.academic_class.name} level
        - Subject: {question_bank.subject.name}
        - Ensure questions are clear, unambiguous, and educational
        - For multiple choice, provide exactly 4 options with one clear correct answer
        - Include brief explanations for correct answers

        Format each question as JSON with this structure:
        {{
            "question_type": "multiple_choice|true_false|short_answer",
            "question_text": "The question text here",
            "options": ["Option A", "Option B", "Option C", "Option D"] (for multiple choice only),
            "correct_answer": "The correct answer or option letter",
            "explanation": "Brief explanation of why this is correct"
        }}

        Return a JSON array of question objects.
        """

        return prompt

    def _call_ai_api(self, prompt: str) -> Dict:
        """Call the AI API"""
        if self.provider.lower() == 'openai':
            return self._call_openai(prompt)
        elif self.provider.lower() == 'claude':
            return self._call_claude(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_openai(self, prompt: str) -> Dict:
        """Call OpenAI API"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': 'gpt-3.5-turbo',
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are an expert educational content creator. Generate high-quality educational questions.'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': 2000,
            'temperature': 0.7
        }

        response = requests.post(
            f'{self.base_url}/chat/completions',
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:
            raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

        return response.json()

    def _call_claude(self, prompt: str) -> Dict:
        """Call Claude API (placeholder - implement based on Claude API docs)"""
        # Implement Claude API call here
        raise NotImplementedError("Claude integration not implemented yet")

    def _parse_ai_response(self, response: Dict) -> List[Dict]:
        """Parse AI API response and extract questions"""
        if self.provider.lower() == 'openai':
            content = response['choices'][0]['message']['content']
        else:
            content = response.get('content', '')

        # Try to extract JSON from the response
        try:
            # Find JSON array in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_content = content[start_idx:end_idx]
                questions_data = json.loads(json_content)
            else:
                # Fallback: try to parse entire content as JSON
                questions_data = json.loads(content)

            if not isinstance(questions_data, list):
                questions_data = [questions_data]

            return questions_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {content}")
            raise Exception(f"Invalid JSON response from AI: {str(e)}")

    def _validate_question_data(self, question_data: Dict) -> bool:
        """Validate generated question data"""
        required_fields = ['question_type', 'question_text', 'correct_answer']

        # Check required fields
        for field in required_fields:
            if field not in question_data or not question_data[field]:
                return False

        # Validate question type
        valid_types = ['multiple_choice', 'true_false', 'short_answer']
        if question_data['question_type'] not in valid_types:
            return False

        # Validate multiple choice questions have options
        if question_data['question_type'] == 'multiple_choice':
            if 'options' not in question_data or len(question_data['options']) != 4:
                return False

        return True

    def _get_model_name(self) -> str:
        """Get the model name used"""
        if self.provider.lower() == 'openai':
            return 'gpt-3.5-turbo'
        elif self.provider.lower() == 'claude':
            return 'claude-3'
        return 'unknown'

    def create_questions_from_ai(
        self,
        questions_data: List[Dict],
        question_bank: QuestionBank,
        teacher
    ) -> Tuple[List[Question], AIGenerationLog]:
        """
        Create Question objects from AI-generated data

        Returns:
            Tuple of (created_questions, generation_log)
        """
        created_questions = []

        for q_data in questions_data:
            try:
                # Create the question
                question = Question.objects.create(
                    question_bank=question_bank,
                    question_type=q_data['question_type'],
                    question_text=q_data['question_text'],
                    explanation=q_data.get('explanation', ''),
                    difficulty_level=question_bank.difficulty_level,
                    marks=1.0  # Default marks
                )

                # Create options for multiple choice questions
                if q_data['question_type'] == 'multiple_choice' and 'options' in q_data:
                    correct_answer = q_data['correct_answer'].upper()
                    for i, option_text in enumerate(q_data['options']):
                        option_letter = chr(65 + i)  # A, B, C, D
                        is_correct = (option_letter == correct_answer)

                        QuestionOption.objects.create(
                            question=question,
                            option_text=option_text,
                            is_correct=is_correct,
                            order=i
                        )

                created_questions.append(question)

            except Exception as e:
                logger.error(f"Failed to create question from AI data: {q_data} - Error: {str(e)}")
                continue

        # Create generation log
        generation_log = AIGenerationLog.objects.create(
            user=teacher,
            model_used=self._get_model_name(),
            topic=question_bank.topic or "General",
            question_count=len(created_questions),
            question_bank=question_bank,
            success=len(created_questions) > 0
        )

        return created_questions, generation_log


def generate_questions_with_ai(
    topic: str,
    question_bank: QuestionBank,
    teacher,
    count: int = 5,
    difficulty: str = 'medium',
    question_types: List[str] = None,
    provider: str = 'openai'
) -> Tuple[List[Question], AIGenerationLog]:
    """
    Convenience function to generate questions with AI

    Args:
        topic: Topic for questions
        question_bank: QuestionBank to add questions to
        teacher: Teacher user who requested generation
        count: Number of questions to generate
        difficulty: Difficulty level
        question_types: Types of questions to generate
        provider: AI provider ('openai', 'claude')

    Returns:
        Tuple of (created_questions, generation_log)
    """
    generator = AIQuestionGenerator(provider=provider)

    try:
        questions_data, model_used = generator.generate_questions(
            topic=topic,
            question_bank=question_bank,
            count=count,
            difficulty=difficulty,
            question_types=question_types
        )

        created_questions, generation_log = generator.create_questions_from_ai(
            questions_data, question_bank, teacher
        )

        return created_questions, generation_log

    except Exception as e:
        # Create error log
        error_log = AIGenerationLog.objects.create(
            user=teacher,
            model_used=generator._get_model_name(),
            topic=topic,
            question_count=0,
            question_bank=question_bank,
            success=False,
            error_message=str(e)
        )
        raise
