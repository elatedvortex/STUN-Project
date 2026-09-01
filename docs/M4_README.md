# M4 — Trainer (PPO / SAC)

Status: **built and passing** (13 trainer tests).

---

## What's here

### `core/`

| File | Class / Symbol | Purpose |
|------|----------------|---------|
| `trainer.py` | `Trainer`, `TrainingResult` | Wraps Stable-Baselines3 PPO/SAC; exposes `train()`, `evaluate()`, `save()`, `load()`, `predict()` |
| `checkpoint.py` | `SchedulerCheckpointCallback` | SB3 `BaseCallback` subclass; saves `.zip` model + `_meta.json` every `save_freq` steps |
| `loop.py` | `EpisodeRunner`, `RandomAgent` | Thin orchestrator for manual episode loops; owns the `Watchdog` lifecycle |

---

## Trainer API

```python
from core.trainer import Trainer

# Create and train
trainer = Trainer(
    env,
    algorithm="ppo",          # "ppo" or "sac"
    checkpoint_dir="data/checkpoints",
    n_steps=256,              # PPO-specific kwargs forwarded to SB3
    batch_size=64,
    n_epochs=4,
)
result = trainer.train(
    total_timesteps=50_000,
    checkpoint_freq=5_000,    # save model every N steps
    eval_episodes=5,
)
print(result.mean_reward, result.elapsed_sec)

# Save / load
trainer.save("data/checkpoints/final")
trainer2 = Trainer.load("data/checkpoints/final.zip", env, algorithm="ppo")

# Predict
obs, _ = env.reset()
action = trainer2.predict(obs, deterministic=True)

# Evaluate
stats = trainer2.evaluate(n_episodes=10)
# {"mean_reward": float, "std_reward": float, "n_episodes": int}
```

---

## Algorithm compatibility

| Algorithm | Action mode | Notes |
|-----------|-------------|-------|
| PPO | discrete (default) | On-policy; works out of the box with `Discrete(n)` action space |
| SAC | continuous | Off-policy; requires `action_mode="continuous"` in `LinuxSchedulerEnv` |

PPO is the recommended default: it is sample-efficient enough for the small parameter spaces in this project (2–8 parameters), and discrete actions make the rollback audit trail simpler.

---

## Checkpoint files

Every `checkpoint_freq` timesteps, two files are written to `checkpoint_dir`:

```
ppo_5000_steps.zip           ← SB3 model weights (safe to Trainer.load())
ppo_5000_steps_meta.json     ← metadata for reproducibility
```

The metadata JSON contains:

```json
{
  "num_timesteps": 5000,
  "algorithm": "ppo",
  "timestamp": "2026-07-18T10:30:00+00:00",
  "n_episodes": 42,
  "training_config": {
    "total_timesteps": 50000,
    "checkpoint_freq": 5000
  }
}
```

---

## EpisodeRunner

`EpisodeRunner` is the manual-loop alternative to letting SB3 drive:

```python
from core.loop import EpisodeRunner, RandomAgent
from safety.watchdog import Watchdog

agent = RandomAgent(env.action_space)
watchdog = Watchdog(rollback_callback=controller.rollback, timeout_sec=30.0)
runner = EpisodeRunner(env, agent, watchdog=watchdog)

stats = runner.run_episode()
# {"total_reward": float, "steps": int, "mean_reward": float,
#  "rollbacks": int, "elapsed_sec": float}
```

The runner starts the watchdog before `env.reset()` and stops it after the episode completes. The agent must call `wd.ping()` (or the env's step must complete) faster than `timeout_sec` to avoid forced rollback.

---

## Training script

```bash
# Dry-run (no real sysctl, 1000 steps, PPO)
python3 scripts/run_training.py --dry-run --timesteps 1000

# Real SAC run with continuous actions
python3 scripts/run_training.py \
    --algorithm sac \
    --action-mode continuous \
    --timesteps 50000 \
    --checkpoint-freq 5000

# Resume from checkpoint
python3 scripts/run_training.py \
    --dry-run \
    --load data/checkpoints/ppo_5000_steps.zip
```

The script currently always uses the safe dry-run backend regardless of `--dry-run` (see `run_training.py` line 114: `if args.dry_run or True`). Remove the `or True` and run as root to enable real sysctl writes.

---

## Test coverage

```
tests/test_trainer.py  (13 tests)
  TestTrainerInit
    test_init_ppo_discrete
    test_init_sac_continuous
    test_unknown_algorithm_raises
  TestTrainerTrain
    test_ppo_short_train_returns_result
    test_sac_short_train_returns_result
    test_train_increments_num_timesteps
  TestTrainerPredict
    test_predict_returns_valid_action
  TestTrainerSaveLoad
    test_save_creates_zip
    test_load_and_predict
  TestTrainerEvaluate
    test_evaluate_returns_expected_keys
  TestCheckpointCallback
    test_checkpoint_zip_files_created
    test_checkpoint_metadata_json_created
    test_metadata_json_has_expected_fields
```

All tests use fake envs and run for 8 timesteps — total test time for M4 is under 15 seconds.

---

## GPU note

SB3 warns that PPO with `MlpPolicy` (vector observations) is better run on CPU:

```
UserWarning: You are trying to run PPO on the GPU...
```

To suppress and force CPU:

```python
trainer = Trainer(env, algorithm="ppo", device="cpu", ...)
```

Or set `CUDA_VISIBLE_DEVICES=""` in the environment before running.

---

## Known gaps / design notes

- TensorBoard logging is supported (`tensorboard_log=...` kwarg to `Trainer`) but disabled by default to keep the test environment clean.
- The `TrainingResult` is returned by `train()` but not persisted to the SQLite DB. A natural extension: write a `run` row to `storage/db.py` on every `trainer.train()` call.
- `Trainer.load()` hard-codes `checkpoint_dir = Path("data/checkpoints")`. A future refactor should read this from the meta JSON.
