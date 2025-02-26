import json
import logging
import os
import sys
import time
import datetime
import random
from typing import Dict, List, Tuple, Optional, Any

import ollama
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG for more detailed logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("millionaire_game.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("millionaire_game")

# Set httpx (used by ollama) to INFO level to reduce verbosity
logging.getLogger("httpx").setLevel(logging.INFO)

# Define money ladder with milestone amounts
MONEY_LADDER = [
    0,          # Starting amount
    100,        # Question 1
    200,        # Question 2
    300,        # Question 3
    500,        # Question 4
    1000,       # Question 5 - First milestone
    2000,       # Question 6
    4000,       # Question 7
    8000,       # Question 8
    16000,      # Question 9
    32000,      # Question 10 - Second milestone
    64000,      # Question 11
    125000,     # Question 12
    250000,     # Question 13
    500000,     # Question 14
    1000000     # Question 15
]

MILESTONES = [1000, 32000]

# Define English language topics
TOPICS = [
    "Grammar - Verb Tenses",
    "Grammar - Prepositions",
    "Grammar - Articles",
    "Grammar - Pronouns",
    "Vocabulary - Synonyms",
    "Vocabulary - Antonyms",
    "Vocabulary - Homophones",
    "Idioms - Common Expressions",
    "Idioms - Figurative Language",
    "Slang - Everyday Usage",
    "Pronunciation - Commonly Mispronounced Words",
    "Punctuation - Correct Usage",
    "Spelling - Commonly Misspelled Words",
    "Phrasal Verbs - Common Combinations",
    "Word Formation - Prefixes and Suffixes"
]

class MillionaireGame:
    def __init__(self, player_name: str, model: str = "llama3.2"):
        """Initialize a new game session."""
        self.player_name = player_name
        self.model = model
        self.current_question_num = 0
        self.current_money = 0
        self.game_over = False
        self.questions_asked = []
        self.used_topics = set()  # Track used topics to avoid repetition
        self.used_questions = set()  # Track used question texts to avoid repetition
        self.fallback_index = 0  # To track which fallback questions have been used
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_file = f"{player_name.replace(' ', '_')}-{self.timestamp}.json"
        logger.info(f"New game started for player: {player_name}")
    
    def generate_question(self) -> Dict[str, Any]:
        """Generate a question using Ollama."""
        try:
            # Select a topic that hasn't been used recently
            available_topics = [topic for topic in TOPICS if topic not in self.used_topics]
            if not available_topics:
                # If all topics have been used, reset and use all topics again
                available_topics = TOPICS
                self.used_topics = set()
            
            topic = random.choice(available_topics)
            self.used_topics.add(topic)  # Mark this topic as used
            
            # Using triple quotes and raw string to avoid format issues
            prompt = r"""
            Create a multiple-choice question for 'Who Wants to be a Millionaire' that tests English language proficiency.

            Topic: """ + topic + r"""
            
            Format your response as valid JSON with these fields:
            - question (string): The question text
            - options (array): Four options as strings labeled with "A. ", "B. ", "C. ", "D. " prefixes
            - correct_answer (string): The letter of the correct option (A, B, C, or D)
            - explanation (string): A clear explanation of why the answer is correct

            IMPORTANT: Each option should be a simple string starting with the letter label, like "A. Option text here".
            Do NOT use nested objects or dictionaries for options.
            Make sure all values are properly quoted in the JSON.

            Example of correct format:
            {
              "question": "What is the past tense of 'go'?",
              "options": [
                "A. Goed",
                "B. Went",
                "C. Gone",
                "D. Going"
              ],
              "correct_answer": "B",
              "explanation": "The irregular past tense of 'go' is 'went'."
            }

            The question should be challenging but fair. Provide good distractors for wrong answers.
            """
            
            logger.info(f"Generating question on topic: {topic}")
            response = ollama.chat(model=self.model, messages=[
                {
                    'role': 'user',
                    'content': prompt,
                }
            ])
            
            content = response.message.content
            logger.debug(f"Raw response from Ollama: {content}")
            
            # Extract JSON from the response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_content = content[json_start:json_end]
                try:
                    # Try to fix common JSON formatting issues
                    # Replace unquoted A, B, C, D with quoted versions
                    fixed_json = json_content
                    for label in ["A", "B", "C", "D"]:
                        fixed_json = fixed_json.replace(f'"label": {label},', f'"label": "{label}",')
                        fixed_json = fixed_json.replace(f'"correct_answer": {label}', f'"correct_answer": "{label}"')
                    
                    logger.debug(f"Attempting to parse JSON: {fixed_json}")
                    question_data = json.loads(fixed_json)
                    question_data['topic'] = topic
                    
                    # Check if this question has been asked before
                    question_text = question_data.get('question', '')
                    if question_text in self.used_questions:
                        logger.info(f"Question already used, generating another one: {question_text}")
                        return self.generate_question()  # Try again with a different question
                    
                    self.used_questions.add(question_text)  # Mark this question as used
                    
                    # Normalize the options format to ensure they're always strings
                    normalized_options = []
                    for option in question_data.get('options', []):
                        if isinstance(option, dict):
                            # If option is a dict with label and text, combine them
                            if 'label' in option and 'text' in option:
                                label = option['label']
                                text = option['text']
                                normalized_options.append(f"{label}. {text}")
                            else:
                                # If it's some other dict format, convert to string
                                normalized_options.append(str(option))
                        else:
                            # If it's already a string, keep as is
                            normalized_options.append(str(option))
                    
                    # Make sure we have at least 4 options
                    while len(normalized_options) < 4:
                        normalized_options.append(f"Option {len(normalized_options) + 1}")
                    
                    question_data['options'] = normalized_options
                    logger.debug(f"Normalized question data: {question_data}")
                    return question_data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from Ollama response: {e}")
                    logger.error(f"Content causing error: {json_content}")
            
            logger.error(f"Failed to extract valid JSON from Ollama response: {content}")
            # Fallback question if Ollama fails
            return self._generate_fallback_question(topic)
            
        except Exception as e:
            logger.error(f"Error generating question: {str(e)}", exc_info=True)
            # Fallback question if Ollama fails
            return self._generate_fallback_question()
    
    def _generate_fallback_question(self, topic: str = "Grammar - Basic") -> Dict[str, Any]:
        """Generate a fallback question if Ollama fails."""
        logger.info(f"Using fallback question for topic: {topic}")
        
        # Large pool of fallback questions to avoid repetition
        fallback_questions = [
            {
                "topic": topic,
                "question": "Which of the following is a correct sentence?",
                "options": [
                    "A. I have been to Paris last year.",
                    "B. I went to Paris last year.",
                    "C. I have went to Paris last year.",
                    "D. I had been going to Paris last year."
                ],
                "correct_answer": "B",
                "explanation": "When using a specific time in the past (last year), the simple past tense is correct. 'I went to Paris last year' is grammatically correct."
            },
            {
                "topic": topic,
                "question": "Which word is a synonym for 'happy'?",
                "options": [
                    "A. Sad",
                    "B. Angry",
                    "C. Joyful",
                    "D. Tired"
                ],
                "correct_answer": "C",
                "explanation": "'Joyful' means full of joy or happiness, making it a synonym for 'happy'."
            },
            {
                "topic": topic,
                "question": "What is the correct spelling?",
                "options": [
                    "A. Accomodate",
                    "B. Acommodate",
                    "C. Accommodate",
                    "D. Acomodate"
                ],
                "correct_answer": "C",
                "explanation": "'Accommodate' is the correct spelling with two 'c's and two 'm's."
            },
            {
                "topic": topic,
                "question": "Which of these is a correct use of the semicolon?",
                "options": [
                    "A. I went to the store; and bought milk.",
                    "B. I went to the store; I bought milk.",
                    "C. I went to the store, I bought milk.",
                    "D. I went to the store; because I needed milk."
                ],
                "correct_answer": "B",
                "explanation": "A semicolon is used to join two independent clauses without a conjunction. Option B correctly uses the semicolon to join two complete sentences."
            },
            {
                "topic": topic,
                "question": "Which sentence contains a dangling modifier?",
                "options": [
                    "A. The teacher explained the problem to the students.",
                    "B. Walking down the street, the birds sang loudly.",
                    "C. She read the book that I recommended.",
                    "D. After finishing the assignment, the student went home."
                ],
                "correct_answer": "B",
                "explanation": "In the sentence 'Walking down the street, the birds sang loudly,' the modifier 'walking down the street' is dangling because birds cannot walk down the street. The subject performing the action is missing."
            },
            {
                "topic": topic,
                "question": "Which of these is the correct plural form of 'child'?",
                "options": [
                    "A. Childs",
                    "B. Childes",
                    "C. Children",
                    "D. Childrens"
                ],
                "correct_answer": "C",
                "explanation": "'Children' is the correct irregular plural form of 'child'. It doesn't follow the regular pattern of adding 's' or 'es'."
            },
            {
                "topic": topic,
                "question": "What is the meaning of the idiom 'to hit the hay'?",
                "options": [
                    "A. To beat someone",
                    "B. To go to sleep",
                    "C. To work in a farm",
                    "D. To exercise vigorously"
                ],
                "correct_answer": "B",
                "explanation": "The idiom 'to hit the hay' means to go to bed or go to sleep. It originated from the days when mattresses were filled with hay."
            },
            {
                "topic": topic,
                "question": "Which sentence uses the correct form of the verb?",
                "options": [
                    "A. Each of the students have completed the assignment.",
                    "B. Neither of my brothers are going to the party.",
                    "C. The team of doctors has arrived at the hospital.",
                    "D. The staff were divided on the issue."
                ],
                "correct_answer": "C",
                "explanation": "In the sentence 'The team of doctors has arrived at the hospital,' the singular subject 'team' correctly takes the singular verb 'has'. 'Team' is a collective noun that's treated as singular when referring to the group as a single unit."
            }
        ]
        
        # Check if we have any previously unused fallback questions
        unused_questions = []
        for question in fallback_questions:
            if question["question"] not in self.used_questions:
                unused_questions.append(question)
        
        # If we've used all fallback questions, reset and use all again
        if not unused_questions:
            unused_questions = fallback_questions
            # Only remove fallback questions from used_questions
            fallback_question_texts = {q["question"] for q in fallback_questions}
            self.used_questions = self.used_questions - fallback_question_texts
        
        # Select a random unused question
        selected_question = random.choice(unused_questions)
        self.used_questions.add(selected_question["question"])  # Mark as used
        
        return selected_question
    
    def display_question(self, question_data: Dict[str, Any]) -> None:
        """Display the question and options to the user."""
        try:
            amount = MONEY_LADDER[self.current_question_num + 1]
            print("\n" + "=" * 60)
            print(Fore.YELLOW + f"Question for ${amount:,}")
            print(Fore.YELLOW + f"Topic: {question_data['topic']}")
            print(Fore.GREEN + f"\n{question_data['question']}\n")
            
            # Make sure options is a list of strings
            if 'options' not in question_data:
                logger.error("Question data doesn't contain 'options' key")
                question_data['options'] = ["A. Missing option", "B. Missing option", 
                                           "C. Missing option", "D. Missing option"]
            
            options = question_data['options']
            for i, option in enumerate(options):
                # Handle if option is not a string
                option_str = str(option)
                print(Fore.CYAN + option_str)
            
            print("=" * 60 + "\n")
        except Exception as e:
            logger.error(f"Error displaying question: {str(e)}", exc_info=True)
            # Print a simplified version as fallback
            print("\n" + "=" * 60)
            print(Fore.YELLOW + "Question:")
            try:
                print(Fore.GREEN + question_data.get('question', 'Missing question'))
                print(Fore.CYAN + "A. Option A")
                print(Fore.CYAN + "B. Option B")
                print(Fore.CYAN + "C. Option C")
                print(Fore.CYAN + "D. Option D")
            except:
                print(Fore.RED + "Error displaying question details")
            print("=" * 60 + "\n")
    
    def process_answer(self, user_answer: str, question_data: Dict[str, Any]) -> bool:
        """Process the user's answer and update game state."""
        try:
            # Validate question_data has the required fields
            if 'correct_answer' not in question_data:
                logger.error("Question data missing 'correct_answer' field")
                question_data['correct_answer'] = "A"  # Default to A if missing
            
            # Normalize the correct answer format (remove any extra characters like periods)
            correct_answer = question_data['correct_answer'].upper().strip()
            if len(correct_answer) > 1:
                correct_answer = correct_answer[0]  # Take only the first character
            
            logger.debug(f"User answer: {user_answer}, Correct answer: {correct_answer}")
            is_correct = user_answer.upper() == correct_answer
            
            if is_correct:
                self.current_question_num += 1
                self.current_money = MONEY_LADDER[self.current_question_num]
                
                print(Fore.GREEN + Back.BLACK + Style.BRIGHT + f"\nCORRECT! You now have ${self.current_money:,}!" + Style.RESET_ALL)
                
                # Display explanation
                print(Fore.WHITE + Back.BLUE + "\nEXPLANATION:" + Style.RESET_ALL)
                explanation = question_data.get('explanation', "No explanation provided.")
                print(Fore.WHITE + explanation + Style.RESET_ALL)
                
                # Record question in history
                self.questions_asked.append({
                    "question_num": self.current_question_num,
                    "question": question_data.get('question', 'Unknown question'),
                    "options": question_data.get('options', []),
                    "user_answer": user_answer.upper(),
                    "correct_answer": correct_answer,
                    "explanation": explanation,
                    "topic": question_data.get('topic', 'Unknown topic'),
                    "amount_won": self.current_money
                })
                
                return True
            else:
                # Determine money to fall back to
                money_to_fall_back = 0
                for milestone in reversed(MILESTONES):
                    if milestone <= self.current_money:
                        money_to_fall_back = milestone
                        break
                
                print(Fore.RED + Back.BLACK + Style.BRIGHT + f"\nI'm sorry, that's incorrect." + Style.RESET_ALL)
                print(Fore.RED + f"The correct answer was {correct_answer}." + Style.RESET_ALL)
                
                # Display explanation
                print(Fore.WHITE + Back.BLUE + "\nEXPLANATION:" + Style.RESET_ALL)
                explanation = question_data.get('explanation', "No explanation provided.")
                print(Fore.WHITE + explanation + Style.RESET_ALL)
                
                # Record question in history
                self.questions_asked.append({
                    "question_num": self.current_question_num + 1,
                    "question": question_data.get('question', 'Unknown question'),
                    "options": question_data.get('options', []),
                    "user_answer": user_answer.upper(),
                    "correct_answer": correct_answer,
                    "explanation": explanation,
                    "topic": question_data.get('topic', 'Unknown topic'),
                    "amount_won": money_to_fall_back
                })
                
                self.current_money = money_to_fall_back
                
                print(Fore.YELLOW + f"\nYou fall back to ${money_to_fall_back:,}" + Style.RESET_ALL)
                self.game_over = True
                return False
        
        except Exception as e:
            logger.error(f"Error processing answer: {str(e)}", exc_info=True)
            print(Fore.RED + "There was an error processing your answer. Please try again." + Style.RESET_ALL)
            return False
    
    def save_session(self) -> None:
        """Save the current game session to a JSON file."""
        try:
            session_data = {
                "player_name": self.player_name,
                "timestamp": self.timestamp,
                "model_used": self.model,
                "final_money": self.current_money,
                "questions_asked": self.questions_asked,
                "game_over": self.game_over,
                "used_topics": list(self.used_topics),  # Convert set to list for JSON serialization
                "used_questions": list(self.used_questions)  # Convert set to list for JSON serialization
            }
            
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=4)
            
            logger.info(f"Game session saved to {self.session_file}")
            print(Fore.GREEN + f"\nGame session saved to {self.session_file}" + Style.RESET_ALL)
        
        except Exception as e:
            logger.error(f"Error saving session: {str(e)}")
            print(Fore.RED + f"\nError saving session: {str(e)}" + Style.RESET_ALL)
    
    @classmethod
    def load_session(cls, filename: str) -> Optional['MillionaireGame']:
        """Load a game session from a JSON file."""
        try:
            with open(filename, 'r') as f:
                session_data = json.load(f)
            
            game = cls(session_data['player_name'], session_data['model_used'])
            game.timestamp = session_data['timestamp']
            game.session_file = filename
            game.current_money = session_data['final_money']
            game.questions_asked = session_data['questions_asked']
            game.game_over = session_data['game_over']
            
            # Extract used questions and topics to avoid repetition
            game.used_questions = set()
            game.used_topics = set()
            for q in game.questions_asked:
                if 'question' in q:
                    game.used_questions.add(q['question'])
                if 'topic' in q:
                    game.used_topics.add(q['topic'])
            
            # Determine current question number based on money won
            for i, amount in enumerate(MONEY_LADDER):
                if amount == game.current_money:
                    game.current_question_num = i
                    break
            
            logger.info(f"Game session loaded from {filename}")
            print(Fore.GREEN + f"\nGame session loaded from {filename}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"Player: {game.player_name}, Money: ${game.current_money:,}" + Style.RESET_ALL)
            
            # Display summary of questions asked
            if game.questions_asked:
                print(Fore.CYAN + "\nQuestions History:" + Style.RESET_ALL)
                for q in game.questions_asked:
                    result = "✓" if q['user_answer'] == q['correct_answer'] else "✗"
                    print(f"{q['question_num']}. {result} ${q['amount_won']:,} - {q['topic']}")
            
            return game
        
        except Exception as e:
            logger.error(f"Error loading session: {str(e)}")
            print(Fore.RED + f"\nError loading session: {str(e)}" + Style.RESET_ALL)
            return None
    
    def display_status(self) -> None:
        """Display the current game status."""
        print("\n" + "-" * 60)
        print(Fore.YELLOW + f"Player: {self.player_name}" + Style.RESET_ALL)
        print(Fore.YELLOW + f"Current Money: ${self.current_money:,}" + Style.RESET_ALL)
        
        # Show next question amount if game is not over
        if not self.game_over and self.current_question_num < len(MONEY_LADDER) - 1:
            next_amount = MONEY_LADDER[self.current_question_num + 1]
            print(Fore.YELLOW + f"Next Question Worth: ${next_amount:,}" + Style.RESET_ALL)
        
        print("-" * 60 + "\n")

def display_welcome() -> None:
    """Display the welcome screen."""
    print("\n" + "=" * 80)
    print(Fore.YELLOW + Back.BLUE + Style.BRIGHT + "WHO WANTS TO BE A MILLIONAIRE - ENGLISH LANGUAGE EDITION" + Style.RESET_ALL)
    print(Fore.CYAN + "Improve your English while winning virtual millions!" + Style.RESET_ALL)
    print("=" * 80 + "\n")

def list_saved_sessions() -> List[str]:
    """List all saved game sessions."""
    try:
        files = [f for f in os.listdir('.') if f.endswith('.json') and '-' in f]
        if not files:
            print(Fore.YELLOW + "No saved sessions found." + Style.RESET_ALL)
        else:
            print(Fore.CYAN + "\nSaved Game Sessions:" + Style.RESET_ALL)
            for i, f in enumerate(files, 1):
                print(f"{i}. {f}")
        return files
    except Exception as e:
        logger.error(f"Error listing saved sessions: {str(e)}")
        print(Fore.RED + f"Error listing saved sessions: {str(e)}" + Style.RESET_ALL)
        return []

def main() -> None:
    """Main function to run the game."""
    display_welcome()
    
    # Initialize game or load saved session
    while True:
        print(Fore.GREEN + "1. Start New Game" + Style.RESET_ALL)
        print(Fore.GREEN + "2. Load Saved Game" + Style.RESET_ALL)
        print(Fore.GREEN + "3. Exit" + Style.RESET_ALL)
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            player_name = input("\nEnter your name: ").strip()
            if not player_name:
                player_name = "Player"
            game = MillionaireGame(player_name)
            break
        elif choice == '2':
            files = list_saved_sessions()
            if not files:
                continue
            
            file_choice = input("\nEnter the number of the session to load (or press Enter to go back): ").strip()
            if not file_choice:
                continue
            
            try:
                file_index = int(file_choice) - 1
                if 0 <= file_index < len(files):
                    game = MillionaireGame.load_session(files[file_index])
                    if game:
                        break
                else:
                    print(Fore.RED + "Invalid choice, please try again." + Style.RESET_ALL)
            except ValueError:
                print(Fore.RED + "Invalid choice, please try again." + Style.RESET_ALL)
        elif choice == '3':
            print(Fore.YELLOW + "\nThank you for playing! Goodbye!" + Style.RESET_ALL)
            sys.exit(0)
        else:
            print(Fore.RED + "Invalid choice, please try again." + Style.RESET_ALL)
    
    # Main game loop
    while not game.game_over:
        game.display_status()
        
        question_data = game.generate_question()
        game.display_question(question_data)
        
        while True:
            user_input = input("Your answer (A/B/C/D) or type EXIT to quit: ").strip().upper()
            
            if user_input in ['A', 'B', 'C', 'D']:
                game.process_answer(user_input, question_data)
                break
            elif user_input == 'EXIT':
                print(Fore.YELLOW + "\nGame ended by player." + Style.RESET_ALL)
                game.game_over = True
                break
            else:
                print(Fore.RED + "Invalid input. Please enter A, B, C, D, or EXIT." + Style.RESET_ALL)
        
        # Save after each question
        game.save_session()
        
        if game.game_over:
            break
        
        # Ask if player wants to continue or cash out
        if game.current_money > 0:
            continue_choice = input(f"\nYou have ${game.current_money:,}. Do you want to continue? (Y/N): ").strip().upper()
            if continue_choice != 'Y':
                print(Fore.GREEN + f"\nCongratulations! You're taking home ${game.current_money:,}!" + Style.RESET_ALL)
                game.game_over = True
                game.save_session()
                break
    
    # End of game
    if game.current_money > 0:
        print(Fore.YELLOW + Back.BLACK + Style.BRIGHT + f"\nGame Over! You won ${game.current_money:,}!" + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + Back.BLACK + Style.BRIGHT + "\nGame Over! Better luck next time!" + Style.RESET_ALL)
    
    # Ask if player wants to play again
    play_again = input("\nWould you like to play again? (Y/N): ").strip().upper()
    if play_again == 'Y':
        main()
    else:
        print(Fore.YELLOW + "\nThank you for playing! Goodbye!" + Style.RESET_ALL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\nGame interrupted. Exiting gracefully..." + Style.RESET_ALL)
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {str(e)}", exc_info=True)
        print(Fore.RED + f"\nAn unexpected error occurred: {str(e)}" + Style.RESET_ALL)
        print(Fore.RED + "Please check the log file for details." + Style.RESET_ALL)
        sys.exit(1)