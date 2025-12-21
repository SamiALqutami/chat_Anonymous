import random
import time
import asyncio
from typing import Dict, List, Optional, Tuple, Set
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

class XOGame:
    def __init__(self, game_id: int, player1: int, player2: Optional[int] = None, is_random: bool = False):
        self.game_id = game_id
        self.player1 = player1
        self.player2 = player2
        self.board = ['⬜'] * 9
        self.current_player = player1
        self.symbols = {player1: '❌'}
        self.status = 'waiting' if player2 is None else 'active'
        self.created_at = time.time()
        self.winner = None
        self.move_history = []
        self.message_ids = {}  # لتخزين معرفات الرسائل
        self.is_random = is_random
        
        if player2:
            self.symbols[player2] = '⭕'
    
    def join(self, player_id: int) -> bool:
        if self.status != 'waiting' or self.player2 is not None:
            return False
        
        self.player2 = player_id
        self.symbols[player_id] = '⭕'
        self.status = 'active'
        return True
    
    def make_move(self, player_id: int, position: int) -> Tuple[bool, str, Optional[int]]:
        if self.status != 'active':
            return False, "اللعبة غير نشطة", None
        
        if self.current_player != player_id:
            return False, "ليس دورك للعب", None
        
        if position < 0 or position > 8:
            return False, "موقع غير صالح", None
        
        if self.board[position] != '⬜':
            return False, "هذه الخانة محجوزة", None
        
        # تنفيذ الحركة
        symbol = self.symbols[player_id]
        self.board[position] = symbol
        self.move_history.append((player_id, position, symbol))
        
        # التحقق من الفوز
        if self.check_win(symbol):
            self.status = 'finished'
            self.winner = player_id
            return True, "فوز", player_id
        
        # التحقق من التعادل
        if '⬜' not in self.board:
            self.status = 'finished'
            self.winner = None
            return True, "تعادل", None
        
        # تبديل الدور
        self.current_player = self.player2 if player_id == self.player1 else self.player1
        return True, "استمرار", None
    
    def check_win(self, symbol: str) -> bool:
        board = self.board
        win_patterns = [
            [0,1,2], [3,4,5], [6,7,8],  # صفوف
            [0,3,6], [1,4,7], [2,5,8],  # أعمدة
            [0,4,8], [2,4,6]            # قطري
        ]
        return any(all(board[i] == symbol for i in pattern) for pattern in win_patterns)
    
    def get_board_display(self) -> str:
        board = self.board
        return f"""
{board[0]}|{board[1]}|{board[2]}
-----
{board[3]}|{board[4]}|{board[5]}
-----
{board[6]}|{board[7]}|{board[8]}
"""
    
    def restart(self):
        self.board = ['⬜'] * 9
        self.current_player = self.player1
        self.status = 'active'
        self.winner = None
        self.move_history = []

class GuessNumberGame:
    def __init__(self, game_id: int, player_id: int):
        self.game_id = game_id
        self.player_id = player_id
        self.number = random.randint(1, 100)
        self.attempts = 0
        self.max_attempts = 10
        self.created_at = time.time()
        self.status = 'active'
    
    def guess(self, number: int) -> Tuple[bool, str, int]:
        self.attempts += 1
        
        if number == self.number:
            self.status = 'finished'
            points = 5  # الفائز يحصل على 5 نقاط
            return True, f"🎉 صحيح! الرقم هو {number}", points
        
        if self.attempts >= self.max_attempts:
            self.status = 'finished'
            penalty = -2  # الخاسر يخسر 2 نقطة
            return True, f"😞 انتهت محاولاتك! الرقم كان {self.number}", penalty
        
        hint = "⬆️ أكبر من ذلك" if number < self.number else "⬇️ أصغر من ذلك"
        remaining = self.max_attempts - self.attempts
        return False, f"{hint}\nالمحاولات المتبقية: {remaining}", 0

class GameManager:
    def __init__(self, db):
        self.db = db
        self.xo_games: Dict[int, XOGame] = {}
        self.guess_games: Dict[int, GuessNumberGame] = {}
        self.waiting_xo_players: Set[int] = set()  # لاعبين ينتظرون خصم XO
        self.xo_search_tasks: Dict[int, asyncio.Task] = {}
    
    def create_xo_game(self, player1: int, player2: Optional[int] = None, is_random: bool = False) -> XOGame:
        game_id = int(time.time() * 1000) + random.randint(1, 999)
        game = XOGame(game_id, player1, player2, is_random)
        self.xo_games[game_id] = game
        
        if player2 is None:
            self.waiting_xo_players.add(player1)
        
        return game
    
    def join_xo_game(self, game_id: int, player2: int) -> Optional[XOGame]:
        if game_id not in self.xo_games:
            return None
        
        game = self.xo_games[game_id]
        if game.join(player2):
            if game_id in self.xo_games and game.player1 in self.waiting_xo_players:
                self.waiting_xo_players.remove(game.player1)
            return game
        
        return None
    
    async def search_xo_opponent(self, player_id: int, context, max_wait: int = 60) -> Optional[int]:
        """البحث عن خصم XO"""
        # التحقق إذا كان هناك لاعب ينتظر
        for waiting_player in list(self.waiting_xo_players):
            if waiting_player != player_id:
                # إزالة اللاعب من قائمة الانتظار
                self.waiting_xo_players.remove(waiting_player)
                return waiting_player
        
        # إذا لم يوجد خصم، يضاف للانتظار
        self.waiting_xo_players.add(player_id)
        
        # إنشاء مهمة بحث
        task = asyncio.create_task(self._wait_for_opponent(player_id, max_wait))
        self.xo_search_tasks[player_id] = task
        
        try:
            opponent = await task
            return opponent
        except asyncio.TimeoutError:
            # إذا انتهى الوقت
            if player_id in self.waiting_xo_players:
                self.waiting_xo_players.remove(player_id)
            return None
        finally:
            if player_id in self.xo_search_tasks:
                del self.xo_search_tasks[player_id]
    
    async def _wait_for_opponent(self, player_id: int, max_wait: int) -> Optional[int]:
        """الانتظار للعثور على خصم"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            # التحقق إذا كان هناك خصم متاح
            for waiting_player in list(self.waiting_xo_players):
                if waiting_player != player_id:
                    self.waiting_xo_players.remove(waiting_player)
                    if player_id in self.waiting_xo_players:
                        self.waiting_xo_players.remove(player_id)
                    return waiting_player
            
            await asyncio.sleep(1)
        
        raise asyncio.TimeoutError()
    
    def get_xo_game(self, game_id: int) -> Optional[XOGame]:
        return self.xo_games.get(game_id)
    
    def delete_xo_game(self, game_id: int):
        if game_id in self.xo_games:
            game = self.xo_games[game_id]
            # إزالة اللاعبين من قائمة الانتظار
            if game.player1 in self.waiting_xo_players:
                self.waiting_xo_players.remove(game.player1)
            if game.player2 and game.player2 in self.waiting_xo_players:
                self.waiting_xo_players.remove(game.player2)
            del self.xo_games[game_id]
    
    def cancel_xo_search(self, player_id: int):
        """إلغاء بحث XO"""
        if player_id in self.waiting_xo_players:
            self.waiting_xo_players.remove(player_id)
        
        if player_id in self.xo_search_tasks:
            self.xo_search_tasks[player_id].cancel()
            del self.xo_search_tasks[player_id]
    
    def create_guess_game(self, player_id: int) -> GuessNumberGame:
        game_id = int(time.time() * 1000) + random.randint(1, 999)
        game = GuessNumberGame(game_id, player_id)
        self.guess_games[game_id] = game
        return game
    
    def get_guess_game(self, game_id: int) -> Optional[GuessNumberGame]:
        return self.guess_games.get(game_id)
    
    def delete_guess_game(self, game_id: int):
        if game_id in self.guess_games:
            del self.guess_games[game_id]
    
    def cleanup_old_games(self, max_age: int = 3600):
        """تنظيف الألعاب القديمة"""
        current_time = time.time()
        
        # تنظيف ألعاب XO القديمة
        xo_to_remove = []
        for game_id, game in self.xo_games.items():
            if current_time - game.created_at > max_age:
                xo_to_remove.append(game_id)
        
        for game_id in xo_to_remove:
            self.delete_xo_game(game_id)
        
        # تنظيف ألعاب التخمين القديمة
        guess_to_remove = []
        for game_id, game in self.guess_games.items():
            if current_time - game.created_at > max_age:
                guess_to_remove.append(game_id)
        
        for game_id in guess_to_remove:
            self.delete_guess_game(game_id)
        
        return len(xo_to_remove) + len(guess_to_remove)

# وظائف المساعدة
def format_xo_board(board: List[str]) -> str:
    """تنسيق لوحة XO للنص"""
    return f"""
{board[0]}|{board[1]}|{board[2]}
-----
{board[3]}|{board[4]}|{board[5]}
-----
{board[6]}|{board[7]}|{board[8]}
"""

def create_xo_keyboard(board: List[str], game_id: int, can_play: bool = True):
    """إنشاء لوحة مفاتيح لعبة XO"""
    buttons = []
    
    # لوحة اللعبة 3x3
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            idx = i + j
            if board[idx] == '⬜' and can_play:
                row.append(InlineKeyboardButton("⬜", callback_data=f"xo_move_{game_id}_{idx}"))
            else:
                row.append(InlineKeyboardButton(board[idx], callback_data=f"xo_view_{game_id}"))
        buttons.append(row)
    
    # أزرار التحكم
    control_buttons = []
    control_buttons.append(InlineKeyboardButton("🔄 إعادة", callback_data=f"xo_restart_{game_id}"))
    control_buttons.append(InlineKeyboardButton("❌ خروج", callback_data=f"xo_exit_{game_id}"))
    buttons.append(control_buttons)
    
    return InlineKeyboardMarkup(buttons)

def create_game_keyboard():
    """لوحة مفاتيح الألعاب"""
    keyboard = [
        [InlineKeyboardButton("🎯 XO العشوائي", callback_data="game_xo_random"),
         InlineKeyboardButton("🎮 XO مع صديق", callback_data="game_xo_friend")],
        [InlineKeyboardButton("🔢 تخمين الرقم", callback_data="game_guess_number"),
         InlineKeyboardButton("🎰 لعبة الحظ", callback_data="game_lucky")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="game_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def calculate_game_rewards(game_type: str, result: str, player_points: int) -> int:
    """حساب مكافآت الألعاب"""
    if game_type == 'xo':
        if result == 'win':
            return 5  # الفائز يكسب 5 نقاط
        elif result == 'lose':
            return -5  # الخاسر يخسر 5 نقاط
        else:
            return 0  # التعادل
    elif game_type == 'guess':
        if result == 'win':
            return 5  # الفوز: +5 نقاط
        elif result == 'lose':
            return -2  # الخسارة: -2 نقاط
        else:
            return 0
    return 0