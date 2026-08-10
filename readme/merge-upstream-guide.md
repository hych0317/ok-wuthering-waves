# 原仓库主分支合并指南

本文用于将原仓库的新代码从 `upstream/master` 合并到保留多账号定制功能的开发分支。目标是持续获得原仓库的新角色、战斗、界面和依赖更新，同时保留本仓库的多账号、登录切换、日常奖励和无音区健壮性修复。

## 一、分支和远端约定

- `upstream`：原仓库 `ok-oldking/ok-wuthering-waves`，只拉取，不向其推送。
- `origin`：个人 fork `<your-account>/ok-wuthering-waves`，开发分支推送到这里。
- `upstream/master`：合并时使用的原仓库主分支。
- `dev`：历史定制开发分支，包含多账号和其他本地改动，但整体代码可能落后于原仓库。
- `upstream-multiaccount`：以原仓库主分支为基线、重新适配多账号功能的集成分支。后续合并优先以该分支或它的后继分支为目标，不要再直接复制旧 `dev` 的整个文件。

不要使用本地 `master` 代替 `upstream/master`。本地 `master` 和 `origin/master` 都可能长期未更新。

## 二、合并原则

1. 以原仓库主分支作为代码结构和公共接口的基准。
2. 多账号功能按行为保留，不按旧文件全文覆盖。
3. 公共基类发生冲突时逐块合并，不能简单选择 `dev` 整文件。
4. 与多账号无关的角色、战斗框架、资源、依赖和 CI 更新默认采用原仓库版本。
5. 测试取两边并集：保留原仓库测试，再补充本地回归测试。
6. 所有推送只明确推送到 `origin`，不要执行 `git push upstream`。

## 三、合并前准备

### 1. 确认工作区干净

```powershell
git status --short --branch
```

如果有源码改动，优先提交后再合并。不要在存在未提交或已暂存改动时开始 merge，否则本地修复和冲突结果会混在一起。

`.okww_last_run`、`desktop.ini`、pytest 临时目录等本地文件不应进入提交。

### 2. 更新远端引用

```powershell
git fetch upstream
git fetch origin
```

确认原仓库最新提交：

```powershell
git log -1 --oneline upstream/master
```

### 3. 创建备份和集成分支

假设长期维护分支是 `upstream-multiaccount`：

```powershell
git switch upstream-multiaccount
git branch backup/upstream-multiaccount-before-merge-YYYYMMDD
git switch -c merge/upstream-YYYYMMDD
```

不要直接在长期维护分支上第一次处理冲突。集成分支验证通过后，再合并回长期维护分支。

### 4. 记录合并前差异

```powershell
git log --left-right --oneline HEAD...upstream/master
git diff --stat upstream/master...HEAD
```

重点检查以下文件：

```powershell
git diff upstream/master...HEAD -- src/task/MultiAccountDailyTask.py
git diff upstream/master...HEAD -- src/task/BaseWWTask.py
git diff upstream/master...HEAD -- src/task/DailyTask.py
git diff upstream/master...HEAD -- src/task/TacetTask.py
```

## 四、开始合并

```powershell
git merge --no-commit --no-ff upstream/master
```

查看冲突：

```powershell
git status
git diff --name-only --diff-filter=U
```

在上述合并方向中：

- `ours` 是当前集成分支，即多账号定制版本。
- `theirs` 是 `upstream/master`，即原仓库版本。

如果合并方向改变，`ours` 和 `theirs` 的含义也会改变。处理冲突前必须先确认当前所在分支。

## 五、逐文件取舍矩阵

| 文件或模块 | 默认基准 | 必须保留或重新适配的本地功能 |
| --- | --- | --- |
| `src/task/MultiAccountDailyTask.py` | 多账号集成分支 | 账号列表、逐账号日常配置、账号执行队列、登录页状态机、账号选择前页面复核与恢复、账号选择超时重试、桌面截图模式、成功运行标记、全部完成后退出。原仓库版本缺少这些功能时，不应整文件采用主分支。 |
| `src/task/BaseWWTask.py` | 原仓库主分支 | 实例与全局登录状态同步、未登录时禁止错误 `Esc`、月卡 OCR 和奖励弹窗处理、体力 OCR 失败检查，以及多账号流程依赖的少量公共辅助方法。必须逐函数合并。 |
| `src/task/DailyTask.py` | 原仓库主分支 | 每次运行重置登录状态、活跃度解析、先领取任务奖励再领取活跃度奖励、邮件和日常页面返回逻辑。逐块检查，不要采用旧 `dev` 整文件。 |
| `src/task/TacetTask.py` | 原仓库主分支 | 无音区数量上限 17、单次体力 60、直接挑战流程、战斗瞬时误退出重试、奖励页体力 OCR 重试、再次挑战和体力不足退出逻辑。需要结合主分支最新副本接口适配。 |
| `src/task/BaseCombatTask.py` | 原仓库主分支 | 默认采用原仓库。只有能明确指出的本地战斗修复才逐块保留，不能整文件采用旧 `dev`。 |
| `src/combat/**`、`src/char/**` | 原仓库主分支 | 与多账号无直接关系，默认采用主分支的新角色和战斗逻辑。 |
| `config.py` | 原仓库主分支 | 确认 `MultiAccountDailyTask` 仍在一次性任务列表中。其他注册项使用主分支。 |
| `assets/**`、`requirements*.txt`、`.github/**` | 原仓库主分支 | 默认使用原仓库，除非存在明确的本地资源或构建需求。 |
| `i18n/**` | 两边合并 | 保留原仓库新增翻译，同时补齐本地新增配置和日志文本，不能整目录覆盖。 |
| `tests/**` | 两边并集 | 保留原仓库测试，并保留登录状态、逐账号配置、无音区重试和奖励领取回归测试。 |
| `.gitignore` | 两边并集 | 保留原仓库规则，并加入 `.okww_last_run`、`desktop.ini` 和确认无用的本地缓存目录。 |
| `okww_start-daily.bat` | 多账号集成分支 | 保留每日分界、重复运行检查、`/f` 强制执行和成功标记环境变量。该文件必须通过 `.gitignore` 例外纳入版本控制。 |

### 每日自动启动脚本

`okww_start-daily.bat` 和 `MultiAccountDailyTask` 共同维护每日运行标记，合并时必须保留以下约束：

- 批处理只能检查现有 `.okww_last_run`，不能在启动 Python 前写入成功日期。
- 批处理通过 `OKWW_DAILY_RUN_MARKER` 和 `OKWW_DAILY_RUN_DATE` 传递标记路径及游戏日期。
- `/f` 可以跳过重复运行、网络和确认检查，但仍必须计算并传递游戏日期。
- `/check` 只验证游戏日期、日志目录和 Conda 环境，不得启动游戏或任务，可用于排查开机环境差异。
- 只有全部账号的日常流程完成后，`MultiAccountDailyTask` 才能原子写入运行标记。
- 登录、账号选择或任一账号日常任务异常时，不得写入标记，否则当天后续自动启动会被错误跳过。
- 由每日脚本启动的实例发生任务异常后，应在错误日志和截图生成后退出，不能留下无窗口 Python 进程占用单实例锁。
- `.okww_last_run` 及临时文件属于本机状态，必须由 `.gitignore` 排除。
- `okww_prompt.ps1` 缺失、Conda 激活失败或 Python 非零退出时，批处理必须给出明确提示，并将启动阶段写入 `logs/okww-start-daily.log`。

如果原仓库新增或重写启动脚本，应以其启动环境和依赖处理为基准，重新应用上述成功标记协议，不能直接恢复“启动前标记”。

## 六、公共基类冲突处理

`BaseWWTask.py` 是风险最高的文件。正确方式是以主分支文件为主体，再逐项重新应用本地行为。

### 登录状态

必须满足以下不变量：

- 多账号点击登录前，全局状态和当前任务实例状态都必须重置为未登录。
- 检测到大世界后，全局状态和当前实例状态都必须更新为已登录。
- 已登录的子任务要能继承全局状态，否则会在 F2、邮件或活动页面等待 600 秒且不按 `Esc`。
- 登录页等待过程中不能因为旧账号的全局状态而反复按 `Esc`。
- 每次打开账号下拉列表前必须再次确认仍处于账号切换面板。
- 账号面板退回已登录或未登录标题页时，必须重新推进到账号切换面板后再点击。
- OCR 未找到账号列表项时应进入有限重试，不能在第一次超时直接抛出 `WaitFailedException`。

重点复核：

- `BaseWWTask.__init__()`
- `BaseWWTask.ensure_main()`
- `BaseWWTask.is_main()`
- `BaseWWTask.wait_login()`
- `MultiAccountDailyTask._login_selected_account()`
- `MultiAccountDailyTask._select_and_login_account()`

### 月卡和遮挡页面

必须保留：

- 较高阈值的月卡模板检测。
- 月卡文本 OCR 辅助识别。
- “点击空白区域关闭”等奖励弹窗 OCR。
- 覆盖层需要时使用真实鼠标点击。
- 只有实际返回大世界后才将月卡处理标记为成功。

不能只依赖低阈值模板，否则邮件或其他页面可能被误识别成月卡。

### 体力读取

`get_stamina()` 读取失败时应返回明确的失败值；`use_stamina()` 不得把失败值当作零体力继续点击。无音区奖励页应进行有限次数重试，超过次数后明确报错。

## 七、无音区冲突处理

主分支可能持续调整 F2 列表、直接挑战、编队页面和奖励页面。因此导航结构采用主分支，以下业务规则必须保留：

- 单次领取消耗按 60 计算，不能沿用凝素领域的 40。
- 战斗逻辑瞬时误判退出后，如果奖励装置不存在，应重试战斗，不能立即结束任务。
- 战斗和寻奖连续失败最多重试有限次数，避免无限循环。
- 奖励页体力 OCR 失败应重试。
- 再次挑战采用主分支当前副本统一流程，不恢复已经废弃的寻路或固定 `F2` 返回流程。

错误截图中如果敌人仍存活、任务进度仍为 `0/4`，说明是战斗误退出，不是奖励领取失败。

## 八、解决冲突的方法

只在确认整个文件应该取某一侧时使用：

```powershell
git restore --ours path/to/file
git restore --theirs path/to/file
git add path/to/file
```

对于 `BaseWWTask.py`、`DailyTask.py`、`TacetTask.py`，通常不能使用整文件 `--ours` 或 `--theirs`，应手工编辑冲突块。

查看冲突三方内容：

```powershell
git show :1:src/task/BaseWWTask.py
git show :2:src/task/BaseWWTask.py
git show :3:src/task/BaseWWTask.py
```

- `:1:` 是共同祖先。
- `:2:` 是 ours。
- `:3:` 是 theirs。

处理一个文件后立即检查并暂存：

```powershell
git diff --check
git add path/to/file
git status
```

不要一次性“接受全部当前更改”或“接受全部传入更改”。

## 九、合并后验证

### 1. 静态检查

存在本地虚拟环境时：

```powershell
.\.venv\Scripts\python.exe -m py_compile src\task\BaseWWTask.py src\task\DailyTask.py src\task\MultiAccountDailyTask.py src\task\TacetTask.py
git diff --check
```

没有 `.venv` 时使用当前项目实际运行环境中的 Python。

### 2. 自动测试

至少运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestWaitLogin.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p TestTacetTaskLogic.py -v
```

如果主分支更新了测试框架，应按主分支方式运行完整测试，并修复测试代码而不是跳过失败。

### 3. 手动场景

必须验证：

1. 从账号切换面板启动，不会直接登录错误账号。
2. 从已登录标题页启动，能够账号登出、打开登录面板并识别当前账号。
3. 从未登录标题页启动，只点击右侧登录入口。
4. 从大世界、月卡、邮件和其他遮挡页面启动，能够回到大世界后再返回登录页。
5. 每个账号使用自己的日常配置，账号队列顺序正确。
6. 日常任务从 F2 或活动页面启动子任务时，能按 `Esc` 返回大世界，不会等待 600 秒。
7. 无音区直接挑战、编队、战斗、60 体力领取和再次挑战完整运行。
8. 战斗瞬时误退出但敌人仍存活时，能够继续战斗而不是寻找奖励后报错。
9. 邮件页面不会被误识别为月卡。
10. 普通 `AutoLoginTask` 行为不受多账号逻辑影响。
11. 自动启动中账号选择失败时不生成当天成功标记，修复后使用 `/f` 可以重新执行。
12. 自动启动完整成功后生成当天标记，第二次普通启动应被批处理跳过。
13. 自动启动任务异常后 Python 实例应自动退出，再次运行脚本不会被旧实例阻塞。
14. 删除或暂时移走 `okww_prompt.ps1` 时，脚本应记录警告并继续启动，而不是闪退。

## 十、完成合并

确认没有未解决冲突：

```powershell
git status
git diff --check
```

创建合并提交：

```powershell
git commit
```

先推送集成分支到个人 fork：

```powershell
git push -u origin merge/upstream-YYYYMMDD
```

在 GitHub 比较集成分支与长期维护分支，确认改动范围后再合并。不要直接推送到 `upstream`。

## 十一、失败恢复

尚未完成 merge 时可以退出：

```powershell
git merge --abort
```

然后回到备份分支重新处理：

```powershell
git switch upstream-multiaccount
git log -1 --oneline backup/upstream-multiaccount-before-merge-YYYYMMDD
```

不要使用 `git reset --hard` 清理冲突，除非已经确认所有未提交改动都可以丢弃。

## 十二、提交前最终清单

- [ ] 合并来源是最新 `upstream/master`，不是本地 `master`。
- [ ] 合并前工作区干净并创建了备份分支。
- [ ] `MultiAccountDailyTask.py` 的逐账号功能完整保留。
- [ ] 公共基类以主分支为主体，只手工保留必要本地行为。
- [ ] 登录状态在全局和任务实例之间正确同步。
- [ ] 账号选择前会复核页面，账号面板意外关闭后能够恢复并重试。
- [ ] 每日运行标记只在全部账号成功后写入，失败不会阻止当天重试。
- [ ] 自动启动任务异常后不会遗留无窗口 Python 实例，启动阶段错误可在 launcher 日志中定位。
- [ ] 月卡、邮件和奖励弹窗不会互相误识别。
- [ ] 自动测试通过。
- [ ] 关键手动场景通过。
- [ ] 未提交 `.okww_last_run`、`desktop.ini` 或测试缓存。
- [ ] 推送目标明确为 `origin`。
