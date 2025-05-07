import pygame
import random
import os
import json
import sys

# Initialize Pygame
game_title = "Blackjack"
pygame.init()
WIDTH, HEIGHT = 1920, 1080
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption(game_title)
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)

# Paths and constants
CARD_FOLDER = r"Cards (large)"
CHIPS_FOLDER = os.getcwd()
CHIP_SAVE_FILE = "chips.json"
STARTING_CHIPS = 100
NUM_DECKS = 6
NUM_AI_PLAYERS = 2

# Card dimensions & positions
CARD_W, CARD_H = 150, 250
CARD_GAP = 170
DEALER_POS = (WIDTH//2 - (CARD_GAP + CARD_W)//2, 100)
HUMAN_POS = (WIDTH//2 - (CARD_GAP + CARD_W)//2, HEIGHT - CARD_H - 100)
AI_POSITIONS = [
    (100, HEIGHT//2 - CARD_H//2),
    (WIDTH - 100 - CARD_W - CARD_GAP, HEIGHT//2 - CARD_H//2)
]
SHOE_POS = (WIDTH - CARD_W - 50, 50)

# Card and chip data
suits = ['hearts','diamonds','clubs','spades']
ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
chip_values = {"chip_black":1000,"chip_green":500,"chip_blue":100,"chip_red":50,"chip_white":25}
chip_button_positions = {"chip_black":(100,900),"chip_green":(220,900),"chip_blue":(340,900),"chip_red":(460,900),"chip_white":(580,900)}

#Game Variables
player_card_queue = []
dealer_card_queue = []
card_draw_timer = 0
CARD_DRAW_INTERVAL = 300  # milliseconds delay between cards
show_count_until = 0  # timestamp in ms
count_check_paused = False  # New flag to delay the count input



# Load images
card_images, chip_images = {}, {}
card_back = pygame.transform.scale(pygame.image.load(os.path.join(CARD_FOLDER, "card_back.png")), (CARD_W, CARD_H))
for suit in suits:
    for rank in ranks:
        file_rank = f"{int(rank):02}" if rank.isdigit() else rank
        path = os.path.join(CARD_FOLDER, f"card_{suit}_{file_rank}.png")
        if os.path.exists(path):
            img = pygame.image.load(path)
            card_images[f"{rank}_{suit}"] = pygame.transform.scale(img, (CARD_W, CARD_H))
for k in chip_values:
    p = os.path.join(CHIPS_FOLDER, f"{k}.png")
    if os.path.exists(p):
        img = pygame.image.load(p)
        chip_images[k] = pygame.transform.scale(img, (100, 100))

# Background
try:
    TABLE_BG = pygame.transform.scale(
        pygame.image.load(os.path.join(CARD_FOLDER, "table_felt.png")),
        (WIDTH, HEIGHT)
    )
except FileNotFoundError:
    TABLE_BG = None

# Game state and phases
show_count = False
insurance_bet = 0
player_hand, dealer_hand = [], []
ai_hands = [[] for _ in range(NUM_AI_PLAYERS)]
player_split_hand = []
split_active = False
round_result = ""
game_phase = "betting"  # "betting", "insurance", "playing", "count_check", "round_over", "game_over"
count_input = ""
current_bet = 0
chip_count = STARTING_CHIPS

# Helper functions
def load_chips():
    if os.path.exists(CHIP_SAVE_FILE):
        try:
            c = json.load(open(CHIP_SAVE_FILE)).get("chips", STARTING_CHIPS)
            return c if c > 0 else STARTING_CHIPS
        except:
            pass
    return STARTING_CHIPS

def save_chips(c):
    json.dump({"chips": c}, open(CHIP_SAVE_FILE, "w"))

chip_count = load_chips()


def draw_card_with_shadow(card, x, y):
    shadow = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 100))
    screen.blit(shadow, (x + 5, y + 5))
    img = card_back if not isinstance(card, tuple) else card_images.get(f"{card[0]}_{card[1]}", card_back)
    screen.blit(img, (x, y))


def draw_hand(hand, x, y, max_width=None):
    n = len(hand)
    if n == 0:
        return

    if max_width is None:
        max_width = WIDTH - x - 50

    # Avoid division by zero or negative gap
    gap = CARD_GAP
    if n > 1:
        total_needed = CARD_W + (n - 1) * CARD_GAP
        if total_needed > max_width:
            gap = max(20, (max_width - CARD_W) // (n - 1))

    for i, c in enumerate(hand):
        if isinstance(c, tuple):  # Valid card
            draw_card_with_shadow(c, x + i * gap, y)


def calculate_hand(hand):
    value, aces = 0, 0
    for r, _ in hand:
        if r in ['J','Q','K']:
            value += 10
        elif r == 'A':
            value += 11
            aces += 1
        else:
            value += int(r)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def create_shoe():
    return [(r, s) for _ in range(NUM_DECKS) for s in suits for r in ranks]

shoe = create_shoe()
random.shuffle(shoe)
used_cards = []

def draw_card(sh_list):
    global shoe
    if len(shoe) < 52:
        shoe = create_shoe()
        random.shuffle(shoe)
        used_cards.clear()
    card = shoe.pop()
    used_cards.append(card)
    return card


def draw_count():
    cnt = 0
    for rank, _ in used_cards:
        if rank in ['2', '3', '4', '5', '6']:
            cnt += 1
        elif rank in ['10', 'J', 'Q', 'K', 'A']:
            cnt -= 1
        # Ignore 7, 8, 9

    decks_remaining = max(len(shoe) / 52, 1)
    tc = cnt / decks_remaining

    txt = font.render(f"Running: {cnt} | True: {tc:.2f}", True, (255,255,0))
    screen.blit(txt, (50, 1000))

# Central draw routine used by main loop and animations
def draw_table():
    # Existing background/table drawing...
    if TABLE_BG:
        screen.blit(TABLE_BG, (0, 0))
    else:
        screen.fill((34,139,34))
        pygame.draw.ellipse(screen, (0,80,0), (50,50, WIDTH-100, HEIGHT-200))
        pygame.draw.ellipse(screen, (0,120,0), (70,70, WIDTH-140, HEIGHT-260))

    # Stats panel (chips, bet display)
    panel = pygame.Surface((300,120), pygame.SRCALPHA)
    panel.fill((0,0,0,120))
    screen.blit(panel, (50,20))
    screen.blit(font.render(f"Chips: {chip_count}", True, (255,255,255)), (60,30))
    screen.blit(font.render(f"Bet: {current_bet}", True, (255,255,255)), (60,70))

    # Dealer hand
    dx, dy = DEALER_POS
    if game_phase in ("count_check", "round_over", "game_over", "insurance", "dealer_drawing"):
        draw_hand(dealer_hand, dx, dy, max_width=800)

    else:
        if dealer_hand:
            draw_card_with_shadow(None, dx, dy)
        if len(dealer_hand) > 1:
            draw_card_with_shadow(dealer_hand[1], dx + CARD_GAP, dy)

    # AI players hands
    for i, ai in enumerate(ai_hands):
        draw_hand(ai, AI_POSITIONS[i][0], AI_POSITIONS[i][1], max_width=300)


    # Human player hand
    draw_hand(player_hand, HUMAN_POS[0], HUMAN_POS[1], max_width=800)


    # Chips visual next to player’s cards (small chips visualizing bet)
    if current_bet > 0:
        chip_x = HUMAN_POS[0] - 20
        chip_y = HUMAN_POS[1] + CARD_H - 40
        draw_bet_chips(current_bet, chip_x, chip_y)

    # Ensure betting chips and buttons ALWAYS drawn explicitly
    if game_phase == "betting":
        for k, pos in chip_button_positions.items():
            screen.blit(chip_images[k], pos)
        if current_bet > 0:
            deal_button.draw(screen)
        clear_button.draw(screen)

    # Playing action buttons
    if game_phase == "playing":
        hit_button.draw(screen)
        stand_button.draw(screen)
        double_button.draw(screen)
        split_button.draw(screen)
        check_count_button.draw(screen)


    # Round/game over button clearly visible
    if game_phase in ("round_over", "game_over"):
        new_round_button.draw(screen)
        result_text = font.render(round_result, True, (255,255,255))
        screen.blit(result_text, (WIDTH//2 - result_text.get_width()//2, HEIGHT//2 - 40))

    # Shoe visual (ensure shoe drawn explicitly)
    x0, y0 = SHOE_POS
    for i in range(min(len(shoe)//20,12)):
        s = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        s.fill((0,0,0,100))
        screen.blit(s, (x0 + i*5 + 5, y0 + i*5 + 5))
        screen.blit(card_back, (x0 + i*5, y0 + i*5))

    # Optional count display
    
    if show_count or game_phase == "betting":
        draw_count()


    if split_active and player_split_hand:
        sx = HUMAN_POS[0] + CARD_GAP * len(player_hand) + 20
        draw_hand(player_split_hand, sx, HUMAN_POS[1], max_width=500)
    
    # Optional count display
    if game_phase in ("round_over", "count_check") or pygame.time.get_ticks() < show_count_until:
        draw_count()


def draw_hand_values():
    # Player
    player_val = calculate_hand(player_hand)
    txt = font.render(f"Player: {player_val}", True, (255, 255, 255))
    screen.blit(txt, (HUMAN_POS[0], HUMAN_POS[1] - 30))

    # Dealer — only show full hand value when it's supposed to be revealed
    if game_phase in ("count_check", "round_over", "game_over", "dealer_drawing"):
        dealer_val = calculate_hand(dealer_hand)
        txt = font.render(f"Dealer: {dealer_val}", True, (255, 255, 255))
        screen.blit(txt, (DEALER_POS[0], DEALER_POS[1] - 40))
    else:
        # Show just one card value (optional, can be removed for full realism)
        if len(dealer_hand) >= 2:
            val = calculate_hand([dealer_hand[1]])  # Just second (visible) card
            txt = font.render(f"Dealer: {val}+?", True, (200, 200, 200))
            screen.blit(txt, (DEALER_POS[0], DEALER_POS[1] - 40))

    # AI Players
    for i, ai in enumerate(ai_hands):
        val = calculate_hand(ai)
        label = font.render(f"AI {i+1}: {val}", True, (255, 255, 255))
        screen.blit(label, (AI_POSITIONS[i][0], AI_POSITIONS[i][1] + CARD_H + 10))
    


def show_temp_count():
    global show_count_until
    show_count_until = pygame.time.get_ticks() + 2000  # Show for 2 seconds


# Pause screen
# Moved out of draw_table to global scope
def pause_game():
    paused = True
    pf = pygame.font.Font(None, 60)
    txt = pf.render("Game Paused. Press ENTER to resume or ESC to exit.", True, (255,255,255))
    while paused:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    paused = False
                elif ev.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
        screen.fill((30,30,30))
        screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2))
        pygame.display.flip()
        clock.tick(30)


    paused = True
    pf = pygame.font.Font(None, 60)
    txt = pf.render("Game Paused. Press ENTER to resume or ESC to exit.", True, (255,255,255))
    while paused:
        screen.fill((30,30,30))
        screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2))
        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    paused = False
                elif ev.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()


#Reset count/shuffle Message 
def show_popup_message(message, duration=2000):
    popup_font = pygame.font.Font(None, 60)
    text = popup_font.render(message, True, (255, 255, 255))
    bg = pygame.Surface((text.get_width() + 40, text.get_height() + 40))
    bg.fill((0, 0, 0))
    bg_rect = bg.get_rect(center=(WIDTH//2, HEIGHT//2))
    text_rect = text.get_rect(center=bg_rect.center)

    screen.blit(bg, bg_rect.topleft)
    screen.blit(text, text_rect.topleft)
    pygame.display.flip()
    pygame.time.delay(duration)


# Round functions
def reset_round():
    global player_hand, dealer_hand, ai_hands, game_phase, insurance_bet, round_result, show_count_until, chip_count, current_bet

    show_count_until = 0  # Hide the count when new round starts
    player_hand.clear()
    dealer_hand.clear()
    for h in ai_hands:
        h.clear()
    insurance_bet = 0
    round_result = ""

    #  Deduct the player's bet now, not later
    save_chips(chip_count)

    # Deal initial cards
    deal_order = [player_hand, dealer_hand] + ai_hands
    for _ in range(2):
        for hand in deal_order:
            hand.append(draw_card(shoe))
            draw_table()
            pygame.display.flip()
            pygame.time.delay(300)

    # Handle blackjack case
    if calculate_hand(player_hand) == 21 and dealer_hand[1][0] != 'A':
        chip_count += int(current_bet * 2.5)  # Original bet already deducted
        save_chips(chip_count)
        game_phase = 'round_over'
    elif dealer_hand[1][0] == 'A':
        game_phase = 'insurance'
    else:
        game_phase = 'playing'


    

def handle_insurance(choice):
    global insurance_bet, chip_count, game_phase, round_result

    if choice == 'Y':
        insurance_bet = min(current_bet // 2, chip_count)
        chip_count -= insurance_bet

    # Dealer already has two cards — check if it's blackjack
    if calculate_hand(dealer_hand) == 21:
        chip_count += insurance_bet * 2
        round_result = 'Dealer blackjack! Insurance pays 2:1.'
        game_phase = 'round_over'
    else:
        round_result = 'No dealer blackjack.'
        game_phase = 'playing'



def finish_round():
    global chip_count, round_result, game_phase, current_bet, card_draw_timer, dealer_card_queue

    # Prevent crashing due to missing hands
    if not isinstance(player_hand, list) or not isinstance(dealer_hand, list):
        round_result = "Error: Internal hand state corrupted."
        game_phase = "game_over"
        current_bet = 0
        save_chips(chip_count)
        return

    if len(player_hand) == 0 or len(dealer_hand) == 0:
        round_result = "Error: Missing cards in hand."
        game_phase = "game_over"
        current_bet = 0
        save_chips(chip_count)
        return

    # Clear any previous dealer draw queue (prevents double-evaluation)
    dealer_card_queue.clear()

    # AI players draw up to 17
    for h in ai_hands:
        while calculate_hand(h) < 17:
            h.append(draw_card(shoe))

    # Queue dealer's draws
    dealer_total = calculate_hand(dealer_hand)
    while dealer_total < 17:
        dealer_card_queue.append(draw_card(shoe))
        dealer_total = calculate_hand(dealer_hand + dealer_card_queue)  # Predict future total

    card_draw_timer = pygame.time.get_ticks()
    game_phase = "dealer_drawing"





# Actions
def hit_action():
    global card_draw_timer
    player_card_queue.append(draw_card(shoe))
    card_draw_timer = pygame.time.get_ticks()  # <-- explicitly reset timer here





def stand_action():
    finish_round()


def double_action():
    global chip_count, current_bet, card_draw_timer, game_phase

    if chip_count >= current_bet:
        chip_count -= current_bet
        current_bet *= 2
        save_chips(chip_count)

        # Queue one more card and change phase
        player_card_queue.append(draw_card(shoe))
        card_draw_timer = pygame.time.get_ticks()
        game_phase = "player_doubling"





def split_action():
    pass  # unchanged

def add_bet(ch):
    global chip_count, current_bet
    v = chip_values[ch]
    if chip_count >= v:
        current_bet += v
        chip_count -= v
        save_chips(chip_count)
    else:
        show_popup_message("Not enough chips for that bet!", duration=1500)



def clear_bet():
    global chip_count, current_bet
    chip_count += current_bet
    current_bet = 0
    save_chips(chip_count)


def deal_action():
    # Always start a new round, even if no bet placed (for testing/dealing)
    reset_round()

def draw_bet_chips(bet, x, y):
    """Draw chips representing the current bet next to the player's cards."""
    sorted_chips = sorted(chip_values.items(), key=lambda x: -x[1])
    spacing = 25  # Small spacing between chips
    chip_scale = 0.4  # Scaling down chips to 40%
    for chip_name, chip_val in sorted_chips:
        chip_img_small = pygame.transform.scale(chip_images[chip_name], (int(100 * chip_scale), int(100 * chip_scale)))
        while bet >= chip_val:
            screen.blit(chip_img_small, (x, y))
            x += spacing
            bet -= chip_val



def handle_new_round_click():
    global game_phase, chip_count, current_bet
    if game_phase == "game_over" and chip_count <= 0:
        chip_count = STARTING_CHIPS
        save_chips(chip_count)
    current_bet = 0
    game_phase = "betting"



# Button class
class Button:
    def __init__(self, rect, text, action):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.color = (70,130,180)
        self.hcolor = (100,149,237)
    def draw(self, surf):
        col = self.hcolor if self.rect.collidepoint(pygame.mouse.get_pos()) else self.color
        pygame.draw.rect(surf, col, self.rect, border_radius=8)
        txt = font.render(self.text, True, (255,255,255))
        surf.blit(txt, txt.get_rect(center=self.rect.center))
    def is_clicked(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(ev.pos):
            self.action()

# Instantiate buttons
hit_button = Button((150, HEIGHT-240, 120,50), "Hit", hit_action)
stand_button = Button((290, HEIGHT-240, 120,50), "Stand", stand_action)
double_button = Button((430, HEIGHT-240, 120,50), "Double", double_action)
split_button = Button((570, HEIGHT-240, 120,50), "Split", split_action)
deal_button = Button((SHOE_POS[0], SHOE_POS[1]+CARD_H+20, 120,50), "Deal", deal_action)
clear_button = Button((SHOE_POS[0], SHOE_POS[1]+CARD_H+90, 120,50), "Clear", clear_bet)
new_round_button = Button((WIDTH//2-60, HEIGHT//2+40, 120,50), "New", handle_new_round_click)
check_count_button = Button((WIDTH - 180, HEIGHT - 80, 160, 50), "Check Count", lambda: show_temp_count())


# --- Main Game Loop ---
running = True
while running:
    current_time = pygame.time.get_ticks()

    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                pause_game()


            elif ev.key == pygame.K_r:
                used_cards.clear()
                shoe = create_shoe()
                random.shuffle(shoe)
                show_popup_message("Deck reshuffled & count reset!")
            elif game_phase == 'insurance' and ev.key in (pygame.K_y, pygame.K_n):
                handle_insurance('Y' if ev.key == pygame.K_y else 'N')
            elif game_phase == 'count_check':
                if ev.key == pygame.K_BACKSPACE:
                    count_input = count_input[:-1]
                elif ev.key == pygame.K_RETURN:
                    running_count = sum(1 if r in ['2','3','4','5','6'] else -1 for r, _ in used_cards)
                    if count_input.lstrip('-').isdigit() and int(count_input) == running_count:
                        round_result = "Correct!"
                        game_phase = "round_over"
                    else:
                        round_result = f"Incorrect! Count was {running_count}. You lose your bet."
                        chip_count = max(0, chip_count - current_bet)
                        current_bet = 0
                        save_chips(chip_count)
                        game_phase = "game_over"
                elif ev.unicode.isdigit() or (ev.unicode == '-' and not count_input):
                    count_input += ev.unicode
            elif count_check_paused and ev.key == pygame.K_SPACE:
                game_phase = "count_check"
                count_check_paused = False


        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if game_phase == "betting":
                for k, pos in chip_button_positions.items():
                    chip_rect = pygame.Rect(*pos, 100, 100)
                    if chip_rect.collidepoint(ev.pos):
                        add_bet(k)
                deal_button.is_clicked(ev)
                clear_button.is_clicked(ev)
            elif game_phase == "playing":
                hit_button.is_clicked(ev)
                stand_button.is_clicked(ev)
                double_button.is_clicked(ev)
                split_button.is_clicked(ev)
                check_count_button.is_clicked(ev)

            elif game_phase in ("round_over", "game_over"):
                new_round_button.is_clicked(ev)

        elif ev.type == pygame.USEREVENT:
            if game_phase == "round_over":
                pygame.time.set_timer(pygame.USEREVENT, 0)
                count_input = ""
                count_check_paused = True  # pause before enabling count input


    # --- Rendering ---
    draw_table()
    draw_hand_values()


    # --- Animate Player Card Queue ---
    if game_phase in ("playing", "player_doubling") and player_card_queue:
        if current_time - card_draw_timer > CARD_DRAW_INTERVAL:
            card = player_card_queue.pop(0)
            player_hand.append(card)
            card_draw_timer = current_time

        if not player_card_queue:
            # If bust after draw
            if calculate_hand(player_hand) > 21:
                finish_round()
            elif game_phase == "player_doubling":
                finish_round()

    # --- Animate Dealer Drawing ---
    elif game_phase == "dealer_drawing":
        if dealer_card_queue:
            if current_time - card_draw_timer > CARD_DRAW_INTERVAL:
                dealer_hand.append(dealer_card_queue.pop(0))
                card_draw_timer = current_time
        else:
            if not player_hand or not dealer_hand:
                round_result = "Error: One or both hands are missing."
                game_phase = "game_over"
                current_bet = 0
                save_chips(chip_count)
            else:
                dealer_value = calculate_hand(dealer_hand)
                player_value = calculate_hand(player_hand)

            if player_value > 21:
                round_result = "Bust! You lose."
                # No payout, already deducted
            elif dealer_value > 21:
                round_result = "Dealer busts! You win!"
                chip_count += current_bet * 2
            elif player_value > dealer_value:
                round_result = "You win!"
                chip_count += current_bet * 2
            elif player_value == dealer_value:
                round_result = "Push."
                chip_count += current_bet
            else:
                round_result = "You lose."
                # No payout

            save_chips(chip_count)
            current_bet = 0
            pygame.time.set_timer(pygame.USEREVENT, 3000)
            game_phase = "round_over"


    # --- Prompts ---
    if game_phase == 'insurance':
        txt = font.render("Insurance? (Y/N)", True, (255,255,255))
        screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2))

    if game_phase == "count_check":
        prompt = font.render("Enter running count:", True, (255,255,255))
        inp = font.render(count_input, True, (255,255,0))
        screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2 - 60))
        screen.blit(inp, (WIDTH//2 - inp.get_width()//2, HEIGHT//2))

    if count_check_paused:
        msg = font.render("Press SPACE to begin count check", True, (255, 255, 255))
        screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2))

    pygame.display.flip()
    clock.tick(30)
pygame.quit()