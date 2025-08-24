"""
Core game logic module for the Merge Tactics bot.
Handles unit deployment, optimization, and game state management.
"""

import cv2
import numpy as np
import time
import logging
from functools import wraps
from config.unit_costs import unit_costs
import os

logger = logging.getLogger(__name__)

class GameLogic:
    def __init__(self, adb_controller, image_processor):
        self.adb = adb_controller
        self.image_processor = image_processor
        self._position_cache = {}
        
    def get_unit_position(self, center, grid_cells, bench_cells):
        """Get the position name for a unit center coordinate with caching"""
        cache_key = f"{center[0]}_{center[1]}"
        if cache_key in self._position_cache:
            return self._position_cache[cache_key]
        
        x, y = center
        for cell in grid_cells:
            x0, y0, x1, y1 = cell["rect"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                self._position_cache[cache_key] = cell["name"]
                return cell["name"]
        for cell in bench_cells:
            x0, y0, x1, y1 = cell["rect"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                self._position_cache[cache_key] = cell["name"]
                return cell["name"]
        self._position_cache[cache_key] = "desconegut"
        return "desconegut"

    def deploy_units(self, screen, composition, elixir_amount, unit_files, unit_imgs, field_imgs, bench_imgs, field_files, bench_files, grid_cells, bench_cells, elixir_rect, threshold=0.8):
        """Optimized unit deployment logic"""
        print("[DEPLOY] Starting optimized deploy...")
        
        if not self.is_bench_empty(screen):
            logger.info("[DEPLOY] Bench not empty, cleaning")
            self.optimize_unit_positions(screen, composition, field_imgs, bench_imgs, field_files, bench_files, grid_cells, bench_cells, threshold)
        else:
            logger.info("[DEPLOY] Bench empty, no cleanup needed")
        
        relevant_templates = []
        relevant_names = []
        
        # Only shop templates for composition units + cheap units
        for i, unit_file in enumerate(unit_files):
            unit_name = os.path.splitext(unit_file)[0]
            unit_cost = unit_costs.get(unit_name, 0)
            if unit_name in composition or unit_cost <= min(3, elixir_amount):
                relevant_templates.append(unit_imgs[i])
                relevant_names.append(('shop', unit_name))
        
        # Always add field/bench for optimization
        relevant_templates.extend(field_imgs)
        relevant_templates.extend(bench_imgs)
        relevant_names.extend([('field', os.path.splitext(f)[0]) for f in field_files])
        relevant_names.extend([('bench', os.path.splitext(f)[0]) for f in bench_files])
        
        all_detections = self.image_processor.find_units_on_screen(screen, relevant_templates, threshold=threshold, min_dist=30)

        field_units = []
        bench_units = []
        available_cards = []
        
        for i, center in all_detections:
            pos_name = self.get_unit_position(center, grid_cells, bench_cells)
            template_type, unit_name = relevant_names[i]
            if template_type == 'shop':
                cost = unit_costs.get(unit_name, 0)
                if cost <= elixir_amount:
                    available_cards.append((unit_name, cost, center))
            elif template_type == 'field' and pos_name.startswith("camp"):
                field_units.append((i, center, unit_name, pos_name))
            elif template_type == 'bench' and pos_name.startswith("banquillo"):
                bench_units.append((i, center, unit_name, pos_name))
        
        print(f"[SUMMARY] Field:{len(field_units)} Bench:{len(bench_units)} Shop:{len(available_cards)} Elixir:{elixir_amount}")

        purchases_made = 0
           
        for _ in range(4):
            available_compo_cards = [card for card in available_cards if card[0] in composition]

            purchased = False
            
            # Buy composition cards
            if available_compo_cards:
                affordable_compo = [card for card in available_compo_cards if card[1] <= elixir_amount]
                if affordable_compo:
                    most_expensive_compo = max(affordable_compo, key=lambda x: x[1])
                    unit_name, cost, center = most_expensive_compo
                    time.sleep(0.4)
                    print(f"[BUY] {unit_name} (cost: {cost})")
                    self.adb.tap(*center)
                    purchases_made += 1

                    elixir_amount -= cost
                    available_compo_cards.remove(most_expensive_compo)
                    purchased = True
            
            else:
                affordable_cards = [card for card in available_cards if card[1] <= 5]
                if affordable_cards:
                    most_expensive = max(affordable_cards, key=lambda x: x[1])
                    unit_name, cost, center = most_expensive
                    
                    print(f"[BUY] Non compo buy: {unit_name} (cost: {cost})")
                    self.adb.tap(*center)
                    purchases_made += 1
                    elixir_amount -= cost
                    purchased = True
                    available_cards.remove(most_expensive)
            
            if not purchased:
                break
            else:
                time.sleep(0.5)
                screen = self.adb.screenshot()

                shop_detections = self.image_processor.find_units_on_screen(
                    screen, unit_imgs, threshold=threshold, min_dist=30
                )
                
                available_cards = []
                for i, center in shop_detections:
                    unit_name = os.path.splitext(unit_files[i])[0]
                    available_cards.append((unit_name, cost, center))
                
                available_compo_cards = [card for card in available_cards if card[0] in composition]
                logger.info(f"[SHOP] Checking new cards: {available_cards}")
                ## Si hi ha cartes de composició disponibles, intentar comprar alguna
                if available_compo_cards:
                    # Opcional: ordenar per cost descendent
                    available_compo_cards.sort(key=lambda x: x[1], reverse=True)

                    for unit_name, cost, center in available_compo_cards:
                        if cost <= elixir_amount:
                            time.sleep(0.4)
                            print(f"[BUY] {unit_name} (cost: {cost})")
                            self.adb.tap(*center)
                            purchases_made += 1
                            elixir_amount -= cost
                            purchased = True
                        else:
                            break
            
            
        print(f"[SUCCESS] {purchases_made} purchases completed")
        return elixir_amount

    def optimize_unit_positions(self, screen, composition, field_imgs, bench_imgs, field_files, bench_files, grid_cells, bench_cells, threshold=0.8):
        """Quick optimization - sell non-composition units if composition units on bench"""
        
        templates = field_imgs + bench_imgs
        names = [('field', os.path.splitext(f)[0]) for f in field_files] + [('bench', os.path.splitext(f)[0]) for f in bench_files]
        
        detections = self.image_processor.find_units_on_screen(screen, templates, threshold=threshold, min_dist=30)
        
        field_units = []
        bench_units = []
        
        for i, center in detections:
            pos_name = self.get_unit_position(center, grid_cells, bench_cells)
            template_type, unit_name = names[i]
            
            if template_type == 'field' and pos_name.startswith("camp"):
                field_units.append((unit_name, center))
            elif template_type == 'bench' and pos_name.startswith("banquillo"):
                bench_units.append((unit_name, center))
        
        # Find composition units on bench and non-composition on field
        compo_bench = [unit for unit in bench_units if unit[0] in composition]
        non_compo_field = [unit for unit in field_units if unit[0] not in composition]
        print("compo_bench", compo_bench)
        print("non_compo_field", non_compo_field)
        if compo_bench and non_compo_field:
            # Sell cheapest non-composition field unit
            cheapest_field = min(non_compo_field, key=lambda x: unit_costs.get(x[0], 0))
            unit_name, center = cheapest_field
            
            print(f"[OPTIMIZE] Selling {unit_name}")
            self.adb.tap(*center)
            time.sleep(0.25)
            
            screen = self.adb.screenshot()
            sell_pos = self.image_processor.find_template(screen, "templates/sell.png")
            if sell_pos:
                print("Found sell button")
                self.adb.tap(*sell_pos)
                time.sleep(0.5)
                return True
        
        return False

    def is_bench_empty(self, screen, bench_rect=None, empty_bench_template=None):
        """Check if bench is completely empty"""
        if not bench_rect or not empty_bench_template:
            return False

        # Extract ROI and convert to grayscale
        x0, y0, x1, y1 = bench_rect
        bench_roi = screen[y0:y1, x0:x1]
        bench_gray = cv2.cvtColor(bench_roi, cv2.COLOR_BGR2GRAY) if bench_roi.ndim == 3 else bench_roi

        # Load and prepare template
        empty_template = cv2.imread(empty_bench_template)
        if empty_template is None:
            return False
        tpl_gray = cv2.cvtColor(empty_template, cv2.COLOR_BGR2GRAY) if empty_template.ndim == 3 else empty_template

        # Resize if necessary
        if bench_gray.shape != tpl_gray.shape:
            tpl_gray = cv2.resize(tpl_gray, (bench_gray.shape[1], bench_gray.shape[0]))

        # Template matching
        res = cv2.matchTemplate(bench_gray, tpl_gray, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(res)

        return min_val <= 0.13
