# Hammer IRView
A graphical viewer for Hammer IR files, particularly placement constraints.

![](assets/example.png)

## Usage

CLI driver patch:

```py
import hammer_irview
...
class ExampleDriver(hammer_irview.IRViewDriverMixin, CLIDriver):
```

Makefile patch:

```makefile
#########################################################################################
# IRView Invocation Flow
#########################################################################################

.PHONY: irv
irv: $(OBJ_DIR)/hammer.d
	$(HAMMER_EXEC) -e $(ENV_YML) $(foreach x,$(INPUT_CONFS) $(GENERATED_CONFS), -p $(x)) --obj_dir $(OBJ_DIR) irv
```

Command:

```sh
make CONFIG=<Config Name> irv
```