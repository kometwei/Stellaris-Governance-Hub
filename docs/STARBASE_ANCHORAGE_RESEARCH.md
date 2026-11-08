# 锚地整备：原生扣费与排队接口调研

后续已另行实现用户授权的“即时清空设施”，见 [恒星基地清空](STARBASE_CLEAR.md)。这不改变本文关于模板复用及原生排队整备的调查结论。

核查日期：2026-11-07。本机 4.5 系列安装文件及当日生成的 `logs/script_documentation`。

**结论：尚未找到能由事件／按钮效果向恒星基地原生模块、建筑施工队列提交订单的可验证接口。本轮不实施锚地整备，不接入中枢，不改游戏设施或当前发布包。**

用户授权条件是正常扣资源、正常排队施工，满足后才做锚地整备，并跳过特殊基地和 Mod 设施。已发现的直接设置接口不足以满足该条件；手动扣费、等待若干天后直接替换，也不能证明是原生施工。

## 本机证据

| 来源 | 已确认内容 | 对锚地整备的意义 |
| --- | --- | --- |
| `logs/script_documentation/effects.log:1854` | `set_starbase_module = { slot = <int> module = <starbase_module> }`，描述为设置槽位中的模块 | 没有说明会扣资源、产生施工订单，也没有队列参数 |
| 同上 `:1858` | `set_starbase_building = { slot = <int> building = <starbase_building> }` | 同样只有直接设置接口 |
| 同上 `:1862`、`:1866` | 模块与建筑移除接口 | 不是替换／建设订单 |
| 同上 `:758` | `queue_actions`，支持作用域仅 fleet | 舰队行动队列不能当作基地设施施工队列 |
| 同上 `:2763` | `set_ship_construction_type = <starbase_type/none>` | 指定施工类型，不是提交模块、建筑订单；没有 slot／module／building 参数 |
| `common/starbase_types/00_starbase_types.txt:1` 起 | 注释说明类型、比例、权重和 `ai_design` 决定 AI 选取的基地配置 | 不能据此断言给玩家基地设置类型就会自动扣费、排队改建；未进行这种实机试验 |
| `logs/script_documentation/triggers.log:1956`、`:1960` | 计数模块／建筑，可包含正在施工者 | 能检查施工中的设施，不代表能添加订单 |
| 同上 `:3190`、`:3194`、`:3198` | 检查当前施工模块／建筑及队列先后关系 | 这些是只读条件接口 |
| `common/starbase_modules/00_starbase_modules.txt:85` | anchorage 定义了 `construction_days`、费用与效果 | 可以读取目标配置和基础费用，缺少下达原生建设订单的接口 |
| `common/starbase_buildings/00_starbase_buildings.txt:439` | naval_logistics_office 定义了费用、工期、科技和“锚地已经存在或在其前排队”的条件 | 真正实施时必须保留队列顺序及前置，不能只把最终设施设置上去 |
| `common/button_effects/example.txt` | 自定义按钮通过 potential／allow／effect 执行脚本 | 没有公开调用原生建设按钮回调的机制 |
| `interface/starbase_view.gui` | 原生模块列表、build_queue_list、取消与优先级按钮 | 界面存在不等于可以从中枢事件窗调用这些原生命令；未找到可复用的效果绑定 |
| `common/scripted_actions/99_README_SCRIPTED_ACTIONS.txt` | 行动使用者为舰队或巨构；部分 specific_behavior 有引擎支持 | 未找到基地设施下单行为 |

原版事件 `events/game_start.txt:1243` 附近使用 `set_starbase_size`、`set_starbase_module`、`set_starbase_building` 配置开局已有基地，可作为“预设设施”的用例，不能作为付费排队施工用例。

## 搜索范围与限制

- 搜索完整的导出效果名称和描述，并交叉检查相关触发器。
- 搜索游戏 `common/` 和 `events/` 中的施工、排队和模块设置用例。
- 检查原版基地界面、自定义按钮示例、scripted_actions 说明与 starbase_types 说明。
- 搜索本机已安装工坊目录中的 `queue_starbase`、`build_starbase_module`、`build_starbase_building`、`construct_starbase`、`add_to_construction_queue`、`queue_building`、`add_starbase_module` 等候选写法，未找到可用实现；另查 UI Overhaul Dynamic 和奇观拓展中的相关舰队队列／施工类型用例。
- 官方论坛定向搜索未取得可核验的相关结果，不把搜索无结果作为“不可能实现”的证明。

未修改或逆向游戏可执行文件，未操作游戏窗口，未进行原生排队实测。结论是当前证据不足，不能声称引擎绝对不支持，也不能宣称功能已实现。

## 恢复实现所需证据

找到明确、可重复的模块／建筑下单接口或原生按钮调用机制后，先验证单个普通基地：

1. 一次操作后按原生报价扣款，并在基地施工队列中出现真实订单。
2. 随游戏时间推进施工，受原版建设速度影响；取消订单后按原生规则处理退款。
3. 能与已有订单共存，正确处理槽位、替换目标及“先锚地、后海军后勤处”的依赖。
4. 检查资源不足、科技不足、交战／占领、所有权变化、保存读档和重复操作。
5. 通过以上单基地验证后，才扩展为中枢中的批量选择、预览和执行；特殊基地、非本国基地、Mod 模块或建筑默认整座排除。

本轮仅新增此调研记录；未新增脚本、周期钩子、收费动作或不可用的中枢入口。

## 后续：接受即时套用后的模板复用可行性

用户随后允许研究通过直接设置接口复用模板，并要求考虑 Mod 槽位、设施与全国唯一限制。此阶段的目标已不同于前述原生排队整备。再次核查得到如下边界：

### 可以据此继续验证的方案

- 构建时扫描播放集的 `common/starbase_modules`、`starbase_buildings`、`starbase_levels`，收录设施标识、基础槽位、槽位类型和限制。必须处理文件覆盖、同名定义、replace_path 和归档 Mod，不能只把各目录条目合并。
- 使用 `count_starbase_modules`、`count_starbase_buildings` 保存“类型及数量”的配置意图；检查时明确排除正在施工的项目。它们支持按类型计数和与变量比较，不依赖逐槽读取。
- 明确含 `empire_limit` 的设施首版全部从可复制集合排除，不猜测动态全国限量公式；来源有这类设施时必须提示模板未包含该项。目标含受保护或限制不明设施时，整座跳过。
- 同时检查 `starbase_limit`、`fits_on_slots`、`cannot_fit_on_slots`、potential、possible、replaceable、abort_construction_trigger 与 destroy_trigger；存在不能正确解释的限制时拒绝套用。设施本身可能提供容量或解锁前置，不能先清空目标再按清空前的容量回填。
- 第一轮原生实验应限于无施工队列、所有设施均已识别、普通基地、相同等级、无受限槽位、无额外容量变化的单个目标。测试前后核对类型数量、实际槽位、限制与保存读档；通过之后再考虑中枢入口和批量执行。

### 新确认的接口缺口

1. `has_starbase_module`／`has_starbase_building` 的导出语法只有类型参数；未找到按 slot 查询的形式，也未找到模块／建筑槽位迭代作用域。因此不能承诺保留源基地各设施的物理槽位顺序。
2. 等级定义给出基础槽位，设施说明还明确支持 `starbase_module_capacity_add` 和 `starbase_building_capacity_add`。但 `effects.log:549` 的 `export_modifier_to_variable` 支持作用域没有列出 starbase。不能直接以“等级槽位＋在基地上导出修正”作为已验证实现。经舰队／舰船作用域读取是否能准确反映基地容量，尚未验证。
3. 未找到通用的“该设施在该目标／槽位可合法安装”触发器。`can_be_upgraded` 不能替代任意设施的安装许可；直接 setter 是否执行原生限制也尚未实测。
4. 不读取逐槽配置时，遇到目标中需要保留的特殊设施，无法可靠定位其槽位并只替换其他槽位。首版应跳过整个目标，而不是声称可以原位保留全部特殊设施。

### 静态扫描结果

对本机安装定义做去注释、逐个顶层区块扫描：126 个模块定义、113 个建筑定义、41 个基地等级定义。模块中 5 项有显式 `empire_limit`，其中 3 项为动态区块；39 项有槽位白名单或黑名单；建筑中 1 项有显式全国限量。统计包含普通基地、星环、方舟等各类设施，不表示这些都可给普通基地使用。

另检查已安装的奇观拓展目录，发现其自有模块、建筑和基地等级定义；检查时该 Mod 不在 `dlc_load.json` 的启用列表内。因此安装目录扫描只用于兼容性例证，不作为当前播放集生效配置。此处没有声称已实现播放集覆盖解析。

**阶段结论：按设施类型及数量保存、即时重建的受限模板存在实现基础；完整逐槽克隆、任意 Mod 动态容量适配和原位保护特殊设施尚无可靠接口证据。此次只做静态核查，未写入模板功能、未改变发布包，也未进行游戏内套用实验。**
