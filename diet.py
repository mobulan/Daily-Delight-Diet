import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import random
import copy
import json
import os
import shutil
from tkcalendar import Calendar
from configparser import ConfigParser
# from PIL import Image, ImageTk  # 导入PIL库


class ModernStyle:
	@staticmethod
	def configure_styles():
		style = ttk.Style()
		style.theme_use('clam')

		style.configure('TFrame', background='#F0F4F8')
		style.configure('Main.TButton',
		                font=('Segoe UI', 12, 'bold'),
		                foreground='white',
		                background='#4A90E2',
		                borderwidth=0,
		                padding=8)
		style.map('Main.TButton',
		          background=[('active', '#357ABD'), ('pressed', '#2A5F93')])

		style.configure('Secondary.TButton',
		                font=('Segoe UI', 10),
		                foreground='#4A90E2',
		                background='#E3F2FD',
		                borderwidth=0,
		                padding=6)
		style.map('Secondary.TButton',
		          background=[('active', '#BBDEFB'), ('pressed', '#90CAF9')])

		style.configure('Header.TLabel',
		                font=('Segoe UI', 14, 'bold'),
		                foreground='#2D3748',
		                background='#F0F4F8')

		style.configure('Body.TLabel',
		                font=('Segoe UI', 12),
		                foreground='#4A5568',
		                background='#F0F4F8')

		style.configure('TEntry',
		                font=('Segoe UI', 12),
		                borderwidth=2,
		                relief='flat',
		                padding=5)
		style.map('TEntry',
		          bordercolor=[('focus', '#4A90E2'), ('!focus', '#CBD5E0')])

		style.configure('Custom.Horizontal.TProgressbar',
		                thickness=20,
		                troughcolor='#E2E8F0',
		                background='#48BB78',
		                lightcolor='#48BB78',
		                darkcolor='#38A169')

		style.configure('Calendar.Treeview',
		                font=('Segoe UI', 10),
		                background='white')


class DishSelector:
	dish_weights = {}

	def __init__(self, excel_file, recent_days=3, penalty=0.3, long_term_reward=1.01):
		self.excel_file = excel_file
		self.dishes = self.load_dishes_from_excel(excel_file)
		self.recent_dishes = []
		self.recent_days = recent_days
		self.penalty = penalty
		self.long_term_reward = long_term_reward
		self.difficulty_mapping = {"易": 1, "中": 0.9, "难": 0.8}
		self.daily_nutrition_target = {}
		self.initialize_dish_weights()
		self.history_file = self.get_history_file_path(excel_file)
		self.history_menus = {}
		self.load_history()
		self.previous_selected_dishes = []
		self.ingredient_inventory = {}
		self.inventory_file = self.get_inventory_file_path(excel_file)
		self.load_inventory()

	def get_history_file_path(self, excel_path):
		base_name = os.path.splitext(os.path.basename(excel_path))[0]
		return os.path.join("data", f"{base_name}_history.txt")

	def load_history(self):
		try:
			if os.path.exists(self.history_file):
				with open(self.history_file, 'r', encoding='utf-8') as f:
					self.history_menus = json.load(f)
		except Exception as e:
			print(f"加载历史记录失败: {e}")
			self.history_menus = {}

	def get_inventory_file_path(self, excel_path):
		base_name = os.path.splitext(os.path.basename(excel_path))[0]
		return os.path.join("data", f"{base_name}_inventory.json")

	def load_inventory(self):
		try:
			if os.path.exists(self.inventory_file):
				with open(self.inventory_file, 'r', encoding='utf-8') as f:
					self.ingredient_inventory = json.load(f)
		except Exception as e:
			print(f"加载材料库失败: {e}")
			self.ingredient_inventory = {}

	def split_ingredients(self, ingredient_str):
		return [ing.strip() for ing in ingredient_str.replace('，', ',').split(',')]

	def update_ingredient_inventory(self, menu):
		for dish in menu:
			ingredients = self.split_ingredients(dish['main_ingredients'])
			for ing in ingredients:
				if ing in self.ingredient_inventory:
					self.ingredient_inventory[ing]['count'] += 1
					self.ingredient_inventory[ing]['total_amount'] += 1
				else:
					self.ingredient_inventory[ing] = {'count': 1, 'total_amount': 1}
		self.save_inventory()

	def save_inventory(self):
		try:
			os.makedirs(os.path.dirname(self.inventory_file), exist_ok=True)
			with open(self.inventory_file, 'w', encoding='utf-8') as f:
				json.dump(self.ingredient_inventory, f, ensure_ascii=False, indent=2)
		except Exception as e:
			print(f"保存材料库失败: {e}")

	def load_dishes_from_excel(self, excel_file):
		df = pd.read_excel(excel_file)
		expected_columns = ['name', 'calories', 'protein', 'fat', 'carb', 'preference', 'difficulty',
		                    'main_ingredients', 'side_ingredients', 'main_protein']
		if not all(col in df.columns for col in expected_columns):
			raise ValueError(f"Excel file must contain columns: {expected_columns}")
		return df.to_dict('records')

	def initialize_dish_weights(self):
		if not DishSelector.dish_weights:
			for dish in self.dishes:
				DishSelector.dish_weights[dish['name']] = self.calculate_initial_weight(dish)

	def calculate_initial_weight(self, dish):
		return dish["preference"] * self.difficulty_mapping[dish["difficulty"]]

	def update_weights(self):
		for dish in self.dishes:
			weight = DishSelector.dish_weights[dish['name']]
			if dish["name"] in self.recent_dishes:
				weight *= self.penalty
			weight *= self.long_term_reward
			DishSelector.dish_weights[dish['name']] = weight

	def weighted_random_choice(self, dishes):
		total_weight = sum(DishSelector.dish_weights[dish['name']] for dish in dishes)
		if total_weight == 0:
			return random.choice(dishes)
		rand_val = random.uniform(0, total_weight)
		cumulative_weight = 0
		for dish in dishes:
			cumulative_weight += DishSelector.dish_weights[dish['name']]
			if rand_val <= cumulative_weight:
				return dish

	def calculate_nutrition_gap(self, current_nutrition):
		gap = {}
		for nutrient in self.daily_nutrition_target:
			gap[nutrient] = self.daily_nutrition_target[nutrient] - current_nutrition[nutrient]
		return gap

	def adjust_weights_for_nutrition(self, nutrition_gap):
		for dish in self.dishes:
			for nutrient, gap in nutrition_gap.items():
				if gap > 0:
					DishSelector.dish_weights[dish['name']] += dish[nutrient] * (
						0.1 if nutrient == "protein" else 0.05 if nutrient == "fat" else 0.08)

	def generate_daily_menu(self, daily_nutrition_target, regenerate=False):
		self.daily_nutrition_target = daily_nutrition_target
		self.update_weights()

		if regenerate:
			for dish in self.previous_selected_dishes:
				DishSelector.dish_weights[dish['name']] *= 0.7

		lunch = self.weighted_random_choice(self.dishes)
		self.recent_dishes.append(lunch["name"])
		if len(self.recent_dishes) > self.recent_days:
			self.recent_dishes.pop(0)

		current_nutrition = {
			"protein": lunch["protein"],
			"fat": lunch["fat"],
			"carb": lunch["carb"]
		}
		nutrition_gap = self.calculate_nutrition_gap(current_nutrition)
		self.adjust_weights_for_nutrition(nutrition_gap)

		available_dishes_for_dinner = [
			dish for dish in self.dishes
			if dish["name"] != lunch["name"] and dish["main_protein"] != lunch["main_protein"]
		]

		if not available_dishes_for_dinner:
			available_dishes_for_dinner = [dish for dish in self.dishes if dish["name"] != lunch["name"]]

		dinner = self.weighted_random_choice(available_dishes_for_dinner)
		self.recent_dishes.append(dinner["name"])
		if len(self.recent_dishes) > self.recent_days:
			self.recent_dishes.pop(0)

		selected_dishes = [lunch, dinner]
		self.previous_selected_dishes = selected_dishes

		DishSelector.dish_weights[lunch['name']] *= 1.05
		DishSelector.dish_weights[dinner['name']] *= 1.05

		return selected_dishes

	def add_menu_to_history(self, date_str, menu):
		self.history_menus[date_str] = copy.deepcopy(menu)
		self.save_history()
		self.update_ingredient_inventory(menu)

	def get_menu_by_date(self, date_str):
		return self.history_menus.get(date_str)

	def save_history(self):
		try:
			os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
			with open(self.history_file, 'w', encoding='utf-8') as f:
				json.dump(self.history_menus, f, ensure_ascii=False, indent=2)
		except Exception as e:
			print(f"保存历史记录失败: {e}")


class NutritionTargetFrame(ttk.Frame):
	def __init__(self, master, default_values):
		super().__init__(master, style='TFrame')

		self.protein_var = tk.StringVar(value=default_values["protein"])
		self.fat_var = tk.StringVar(value=default_values["fat"])
		self.carb_var = tk.StringVar(value=default_values["carb"])

		protein_frame = ttk.Frame(self, style='TFrame')
		ttk.Label(protein_frame, text="蛋白质（g）:", style='Body.TLabel').pack(side=tk.LEFT)
		ttk.Entry(protein_frame, textvariable=self.protein_var, width=8, style='TEntry').pack(side=tk.LEFT, padx=5)
		protein_frame.pack(side=tk.LEFT, padx=10)

		fat_frame = ttk.Frame(self, style='TFrame')
		ttk.Label(fat_frame, text="脂肪（g）:", style='Body.TLabel').pack(side=tk.LEFT)
		ttk.Entry(fat_frame, textvariable=self.fat_var, width=8, style='TEntry').pack(side=tk.LEFT, padx=5)
		fat_frame.pack(side=tk.LEFT, padx=10)

		carb_frame = ttk.Frame(self, style='TFrame')
		ttk.Label(carb_frame, text="碳水（g）:", style='Body.TLabel').pack(side=tk.LEFT)
		ttk.Entry(carb_frame, textvariable=self.carb_var, width=8, style='TEntry').pack(side=tk.LEFT, padx=5)
		carb_frame.pack(side=tk.LEFT, padx=10)

	def get_values(self):
		try:
			return {
				"protein": float(self.protein_var.get()),
				"fat": float(self.fat_var.get()),
				"carb": float(self.carb_var.get())
			}
		except ValueError:
			return None


class ProgressBarFrame(ttk.Frame):
	def __init__(self, master):
		super().__init__(master, style='TFrame')

		self.protein_bar = ttk.Progressbar(self, style='Custom.Horizontal.TProgressbar')
		self.fat_bar = ttk.Progressbar(self, style='Custom.Horizontal.TProgressbar')
		self.carb_bar = ttk.Progressbar(self, style='Custom.Horizontal.TProgressbar')

		self.protein_label = ttk.Label(self, text="蛋白质: 0%", style='Body.TLabel')
		self.fat_label = ttk.Label(self, text="脂肪: 0%", style='Body.TLabel')
		self.carb_label = ttk.Label(self, text="碳水: 0%", style='Body.TLabel')

		self.protein_label.grid(row=0, column=0, pady=5, sticky='w')
		self.protein_bar.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
		self.fat_label.grid(row=1, column=0, pady=5, sticky='w')
		self.fat_bar.grid(row=1, column=1, padx=10, pady=5, sticky='ew')
		self.carb_label.grid(row=2, column=0, pady=5, sticky='w')
		self.carb_bar.grid(row=2, column=1, padx=10, pady=5, sticky='ew')

		self.columnconfigure(1, weight=1)

	def update_progress(self, protein_percent, fat_percent, carb_percent):
		self.protein_bar['value'] = protein_percent
		self.fat_bar['value'] = fat_percent
		self.carb_bar['value'] = carb_percent

		self.protein_label.config(text=f"蛋白质: {protein_percent:.1f}%")
		self.fat_label.config(text=f"脂肪: {fat_percent:.1f}%")
		self.carb_label.config(text=f"碳水: {carb_percent:.1f}%")


class MenuApp:
	def __init__(self, master):
		self.master = master
		master.title("每日菜单推荐")
		# 使用DPI自适应
		self.dpi = master.winfo_fpixels('1i')
		master.geometry(f"{int(800 * self.dpi / 96)}x{int(850 * self.dpi / 96)}")  # 调整窗口大小
		ModernStyle.configure_styles()

		master.configure(bg='#F0F4F8')
		# 使用grid布局，并让main_frame可以随窗口缩放
		self.main_frame = ttk.Frame(master, style='TFrame')
		self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)  # 减少边距

		self.selector = None
		self.current_generated_menu = None
		self.default_nutrition = {
			"protein": 70,
			"fat": 50,
			"carb": 100
		}
		self.last_excel_path = ""
		self.load_config()
		self.create_widgets()
		self.try_load_last_excel()
		self.inventory_visible = False

		# 在NutritionTargetFrame后创建材料库按钮
		# self.create_inventory_button() # 移到create_widgets里
		self.create_inventory_widgets()

	def create_widgets(self):

		# 1. Excel文件选择按钮 和 显示/隐藏材料库 按钮
		self.top_button_frame = ttk.Frame(self.main_frame, style='TFrame')
		self.select_file_button = ttk.Button(self.top_button_frame,
		                                     text="选择 Excel 文件",
		                                     command=self.select_excel_file,
		                                     style='Main.TButton')
		self.show_inventory_button = ttk.Button(self.top_button_frame,
		                                        text="显示/隐藏材料库",
		                                        command=self.toggle_inventory,
		                                        style='Secondary.TButton')

		self.select_file_button.pack(side=tk.LEFT, expand=True, fill='x', padx=(0, 5))  # 左侧，填充x方向
		self.show_inventory_button.pack(side=tk.LEFT, expand=True, fill='x', padx=(5, 0))  # 右侧, 填充x方向
		self.top_button_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 5))

		# 设置权重，使得select_file_button占2/3，show_inventory_button占1/3
		self.top_button_frame.columnconfigure(0, weight=2)  # select_file_button
		self.top_button_frame.columnconfigure(1, weight=1)  # show_inventory_button

		# 2. 营养目标输入框
		self.nutrition_frame = NutritionTargetFrame(self.main_frame, self.default_nutrition)
		self.nutrition_frame.grid(row=1, column=0, sticky='ew', pady=(0, 5))

		# 3. 生成和重新生成按钮
		self.button_frame = ttk.Frame(self.main_frame, style='TFrame')
		self.generate_button = ttk.Button(self.button_frame,
		                                  text="生成菜单",
		                                  command=self.generate_menu,
		                                  style='Main.TButton',
		                                  state=tk.DISABLED)
		self.regenerate_button = ttk.Button(self.button_frame,
		                                    text="重新生成",
		                                    command=lambda: self.generate_menu(regenerate=True),
		                                    style='Main.TButton',
		                                    state=tk.DISABLED)
		self.generate_button.pack(side='left', padx=5, expand=True, fill='x')
		self.regenerate_button.pack(side='left', padx=5, expand=True, fill='x')
		self.button_frame.grid(row=2, column=0, sticky='ew', pady=(0, 5))

		# 4. 菜单展示区域
		self.menu_frame = ttk.Frame(self.main_frame, style='TFrame')
		self.menu_left = ttk.Frame(self.menu_frame, style='TFrame')
		self.menu_right = ProgressBarFrame(self.menu_frame)

		self.lunch_label = ttk.Label(self.menu_left,
		                             text="",
		                             style='Header.TLabel',
		                             anchor='w')
		self.dinner_label = ttk.Label(self.menu_left,
		                              text="",
		                              style='Header.TLabel',
		                              anchor='w')
		self.lunch_label.pack(fill='x', pady=5)
		self.dinner_label.pack(fill='x', pady=5)

		self.menu_left.pack(side='left', fill='both', expand=True, padx=(0, 10))
		self.menu_right.pack(side='right', fill='both', expand=True, padx=(10, 0))
		self.menu_frame.grid(row=3, column=0, sticky='ew', pady=(0, 5))

		# 5. 确认菜单按钮
		self.confirm_button = ttk.Button(self.main_frame,
		                                 text="确认菜单",
		                                 command=self.confirm_menu,
		                                 style='Main.TButton',
		                                 state=tk.DISABLED)
		self.confirm_button.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(0, 5))

		# 6. 日历控件
		self.cal = Calendar(
			self.main_frame,
			font=('Segoe UI', 12),
			background='#4A90E2',
			bordercolor='#CBD5E0',
			headersbackground='#4A90E2',
			headersforeground='white',
			normalbackground='white',
			weekendbackground='#F0F4F8',
			othermonthbackground='#F8FAFC',
			othermonthwebackground='#F8FAFC',
			selectbackground='#4A90E2',
			selectforeground='white',
			weekendforeground='#4A5568',
			headerfont=('Segoe UI', 14, 'bold'),
			showweeknumbers=False
		)

		self.cal.grid(row=5, column=0, sticky='nsew', pady=(0, 5))
		self.cal.bind("<<CalendarSelected>>", lambda e: self.show_history())

		# 7. 历史记录文本框
		self.history_text = tk.Text(self.main_frame,
		                            height=8,
		                            font=('Segoe UI', 11),
		                            bg='white',
		                            fg='#4A5568',
		                            relief='flat',
		                            padx=10,
		                            pady=10)
		self.history_text.grid(row=6, column=0, sticky='nsew', pady=(0, 5))

		# 设置行列权重，使得内容可以扩展
		self.main_frame.columnconfigure(0, weight=1)
		self.main_frame.rowconfigure(5, weight=1)  # 日历部分
		self.main_frame.rowconfigure(6, weight=1)  # 历史记录部分

	# def create_inventory_button(self): # 移到create_widgets里
	#     self.show_inventory_button = ttk.Button(self.main_frame,
	#                                            text="显示/隐藏材料库",
	#                                            command=self.toggle_inventory,
	#                                            style='Secondary.TButton')
	#     self.show_inventory_button.grid(row=1, column=1, sticky='e', padx=(10,0), pady=(0, 5))  # 位于营养目标右侧

	def create_inventory_widgets(self):
		self.inventory_text = tk.Text(self.main_frame,
		                              height=8,  # 调整高度
		                              font=('Segoe UI', 11),
		                              bg='white',
		                              fg='#4A5568',
		                              relief='flat',
		                              padx=10,
		                              pady=10)
		self.inventory_text.grid(row=7, column=0, sticky='nsew', pady=(0, 10))
		self.inventory_text.grid_remove()  # 初始状态隐藏

		self.main_frame.rowconfigure(7, weight=0)  # 材料库

	def toggle_inventory(self):
		self.inventory_visible = not self.inventory_visible
		if self.inventory_visible:
			self.show_inventory()
			self.inventory_text.grid()
		else:
			self.inventory_text.grid_remove()

	def show_inventory(self):
		inventory_str = "材料库：\n\n"
		if self.selector:
			for ingredient, data in self.selector.ingredient_inventory.items():
				inventory_str += f"{ingredient}: 使用次数 {data['count']}, 总量 {data['total_amount']}\n"

		self.inventory_text.config(state=tk.NORMAL)
		self.inventory_text.delete("1.0", tk.END)
		self.inventory_text.insert(tk.END, inventory_str)
		self.inventory_text.config(state=tk.DISABLED)

	def load_config(self):
		self.config = ConfigParser()
		self.config.read('config.ini')
		if 'DEFAULT' in self.config:
			self.last_excel_path = self.config['DEFAULT'].get('last_excel', '')

	def save_config(self):
		self.config['DEFAULT'] = {'last_excel': self.last_excel_path}
		with open('../config.ini', 'w') as configfile:
			self.config.write(configfile)

	def backup_excel_file(self, src_path):
		try:
			os.makedirs("data", exist_ok=True)
			dst_path = os.path.join("data", os.path.basename(src_path))
			if not os.path.exists(dst_path):
				shutil.copyfile(src_path, dst_path)
			return dst_path
		except Exception as e:
			messagebox.showerror("错误", f"文件备份失败: {e}")
			return src_path

	def try_load_last_excel(self):
		if self.last_excel_path and os.path.exists(self.last_excel_path):
			try:
				self.selector = DishSelector(self.last_excel_path)
				self.generate_button.config(state=tk.NORMAL)
				self.regenerate_button.config(state=tk.NORMAL)
				self.confirm_button.config(state=tk.NORMAL)
				messagebox.showinfo("提示", f"已自动加载上次的菜单文件: {os.path.basename(self.last_excel_path)}")
			except Exception as e:
				messagebox.showerror("错误", f"自动加载失败: {e}")

	def select_excel_file(self):
		file_path = filedialog.askopenfilename(
			title="选择 Excel 文件",
			filetypes=[("Excel 文件", "*.xlsx;*.xls")]
		)
		if file_path:
			try:
				backed_path = self.backup_excel_file(file_path)
				self.last_excel_path = backed_path
				self.save_config()

				self.selector = DishSelector(backed_path)
				self.generate_button.config(state=tk.NORMAL)
				self.regenerate_button.config(state=tk.NORMAL)
				self.confirm_button.config(state=tk.NORMAL)
				self.lunch_label.config(text="")
				self.dinner_label.config(text="")
				messagebox.showinfo("提示", "文件已自动备份到data目录")
			except Exception as e:
				messagebox.showerror("错误", f"加载 Excel 文件失败:\n{e}")

	def generate_menu(self, regenerate=False):
		nutrition_target = self.nutrition_frame.get_values()
		if not nutrition_target:
			messagebox.showerror("错误", "请输入有效的营养目标值")
			return

		try:
			selected_dishes = self.selector.generate_daily_menu(nutrition_target, regenerate=regenerate)
			self.current_generated_menu = selected_dishes

			self.lunch_label.config(
				text=f"午餐：{selected_dishes[0]['name']} ({selected_dishes[0]['main_protein']})")
			self.dinner_label.config(
				text=f"晚餐：{selected_dishes[1]['name']} ({selected_dishes[1]['main_protein']})")

			total = {
				"protein": selected_dishes[0]['protein'] + selected_dishes[1]['protein'],
				"fat": selected_dishes[0]['fat'] + selected_dishes[1]['fat'],
				"carb": selected_dishes[0]['carb'] + selected_dishes[1]['carb']
			}

			protein_percent = (total['protein'] / nutrition_target['protein']) * 100
			fat_percent = (total['fat'] / nutrition_target['fat']) * 100
			carb_percent = (total['carb'] / nutrition_target['carb']) * 100

			self.menu_right.update_progress(protein_percent, fat_percent, carb_percent)

		except AttributeError:
			messagebox.showerror("错误", "请先选择有效的Excel文件")

	def confirm_menu(self):
		selected_date = self.cal.get_date()
		if self.current_generated_menu:
			self.selector.add_menu_to_history(selected_date, self.current_generated_menu)
			messagebox.showinfo("成功", f"{selected_date}的菜单已保存！")
			self.show_history()
		else:
			messagebox.showwarning("警告", "请先生成菜单再确认")

	def show_history(self):
		selected_date = self.cal.get_date()
		menu = self.selector.get_menu_by_date(selected_date) if self.selector else None

		self.history_text.config(state=tk.NORMAL)
		self.history_text.delete("1.0", tk.END)

		if menu:
			lunch, dinner = menu
			history_str = (
				f"{selected_date} 菜单：\n\n"
				f"午餐：{lunch['name']} ({lunch['main_ingredients']})\n"
				f"蛋白质: {lunch['protein']}g 脂肪: {lunch['fat']}g 碳水: {lunch['carb']}g\n\n"
				f"晚餐：{dinner['name']} ({dinner['main_ingredients']})\n"
				f"蛋白质: {dinner['protein']}g 脂肪: {dinner['fat']}g 碳水: {dinner['carb']}g"
			)
		else:
			history_str = f"{selected_date} 无历史菜单"

		self.history_text.insert(tk.END, history_str)
		self.history_text.config(state=tk.DISABLED)


if __name__ == "__main__":
	root = tk.Tk()
	app = MenuApp(root)
	root.mainloop()
