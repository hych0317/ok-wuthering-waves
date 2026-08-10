
from ok import CannotFindException, Logger
from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Farms the selected Tacet Suppression, until no stamina. Must be able to teleport (F2)."
        self.name = "🌊 Tacet Suppression"
        self.support_schedule_task = True
        default_config = {
            'Which Tacet Suppression to Farm': 1,  # starts with 1
        }
        self.total_number = 17
        self.target_enemy_time_out = 10
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0: [],
            1: [],
            2: [],
            3: [],
            4: [],
            5: [],
            6: [],
            7: [["a", 0.3]],
            8: [["d", 0.6]],
            9: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }
        self.stamina_once = 60

    def run(self):
        super().run()
        self.ensure_main(time_out=180)
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self, daily=False, used_stamina=0, config=None):
        if config is None:
            config = self.config
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        self.info_incr('used stamina', 0)
        fail_count = 0
        direct_challenge = False
        while True:
            self.sleep(1)
            if not direct_challenge:
                self.openF2Book("gray_book_boss")
                current, back_up, total = self.get_stamina()
                if current == -1:
                    self.click_relative(0.04, 0.4, after_sleep=1)
                    current, back_up, total = self.get_stamina()
                if total < self.stamina_once:
                    return self.not_enough_stamina()

                self.open_boss_book('wuyin')
                index = config.get('Which Tacet Suppression to Farm', 1) - 1
                direct_challenge = bool(self.teleport_to_tacet(index))
                self.click_team_challenge()
            try:
                self.wait_in_team_and_world(time_out=120)
                self.combat_once(target=True)
                self.sleep(3)
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
                self.sleep(2)
                if not self.has_claim_stamina():
                    self.esc_cancel()
                    self.log_info('is not claim treasure, restart challenge')
                    continue
            except CharRevivedException:
                direct_challenge = False
                self.log_info('farm_tacet: death recovered, re-enter from F2 book')
                continue
            except Exception as e:
                fail_count += 1
                self.log_error(f'farm_tacet: Exception, retry fail_count:{fail_count}', e)
                if fail_count <= 3:
                    continue
                raise

            fail_count = 0
            can_continue, used = self.use_tacet_stamina(must_use)
            self.info_incr('used stamina', used)
            self.sleep(4)
            if not can_continue:
                self.log_info('used all stamina, leave Tacet challenge')
                self.click_relative(0.365, 0.853, hcenter=True)
                self.wait_in_team_and_world(time_out=120)
                return

            must_use -= used
            self.click_relative(0.640, 0.851, hcenter=True, after_sleep=0.2)
            self.wait_click_skip_dialog_confirm()
            if direct_challenge:
                self.wait_in_team_and_world(time_out=120)
                self.sleep(1)
                continue

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def use_tacet_stamina(self, must_use):
        for attempt in range(1, 4):
            try:
                return self.use_stamina(once=self.stamina_once, must_use=must_use)
            except CannotFindException:
                self.log_warning(f'cannot read stamina on reward page, retry {attempt}/3')
                self.sleep(1)
        raise CannotFindException('cannot read stamina on Tacet reward page')

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        return self.click_on_book_target(index + 1, self.total_number)
