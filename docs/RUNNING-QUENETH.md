# Running Queneth smoothly — cheat sheet

Everything you need to start, check, reset and present Queneth in the Ubuntu VM,
without help. First-time setup is in [VM-SETUP.md](VM-SETUP.md); this page is for
every day after that.

Run every command from the project folder:

```bash
cd ~/Queneth
```

## The five commands

| What you want | Command | Time |
| --- | --- | --- |
| Start Queneth (for presenting) | `vm/start.sh --prod` | ~2 min |
| Check it's healthy | `vm/status.sh` | instant |
| Stop it | `vm/stop.sh` | instant |
| Clean store (0 orders) and start | `vm/reset.sh` | ~2 min |
| Same, but keep a copy of the current store | `vm/reset.sh --keep` | ~2 min |

Then open **http://localhost:3000** in the VM's browser. The API's docs are at
http://localhost:8000/docs.

- Closing the terminal does **not** stop Queneth. Only `vm/stop.sh` does.
- Rebooting the VM **does** stop it. Run `vm/start.sh --prod` again after a reboot.
- `vm/start.sh` without `--prod` starts development mode (faster to start, slower
  to use, shows a Next.js overlay). Use it only when changing code.

## Sign-in accounts

Password for all: `Queneth#2026` · QueWallet PIN: `123456` · buyers start with QC 50,000.

| Account | Type | Use it for |
| --- | --- | --- |
| `buyer@queneth.test`, `collector@queneth.test` | Buyer | Shopping, bag, Buy now, checkout, orders, reviews |
| `bench@queneth.test`, `nike@queneth.test`, `penshoppe@queneth.test` | Seller | Seller Studio: products, orders, launches, earnings |
| `admin@queneth.test` | Admin | Control Room: sellers, users, wallet, moderation |

## Presentation day checklist

1. **Before turning on the VM** (once): give it 4 CPUs and 8 GB RAM (see "Make the VM faster" below).
2. Plug the laptop into power. Close heavy apps on the laptop.
3. Start the VM, open a terminal, then:

   ```bash
   cd ~/Queneth
   vm/reset.sh
   ```

4. Wait for `Queneth is running.`, then run `vm/status.sh`. You want:
   `API up`, `Storefront up (prod mode)`, `api.log: clean`, `web.log: clean`.
5. Open http://localhost:3000 and click through the home page, one product page
   and the sign-in page once, so the first real load is fast.
6. Close apps you don't need inside the VM (other browsers, editors, chat apps).

### Suggested demo walkthrough (about 10 minutes)

1. **buyer@**: browse a category → open Bench's *Pique Polo* → size **M** →
   **Add to Bag**. Open another product → **Buy now** (checks out only that piece).
2. **Bag → Checkout with QueWallet**: address → review → PIN `123456` → **Pay**.
   The order shows *Held in escrow*.
3. Sign out → **bench@** → **Seller Studio → Orders**: *Start preparing* →
   *Ship* (tracking number, 6–40 letters/digits/dashes, e.g. `LBC-12345678`) →
   *Mark delivered*.
4. Sign back in as **buyer@** → **Account → Orders** → **I received it** → leave a review.
5. **admin@** → **Control Room → QueWallet → Run reconciliation** (zero drift) and
   **Integrations → Sent emails** (order emails in mock mode).
6. Show the account separation: sellers and admins have no bag or wishlist.

After rehearsing, run `vm/reset.sh` again so you present with a clean store.

## Make the VM faster

### In VirtualBox (VM powered off) — biggest improvement

| Setting | Set to |
| --- | --- |
| System → Motherboard → Base Memory | **8192 MB** (6144 MB if the laptop has only 8 GB) |
| System → Processor → CPUs | **4** (stay in the green zone) |
| System → Processor → Execution Cap | 100% |
| Display → Screen → Video Memory | **128 MB** |
| Display → Graphics Controller | **VMSVGA**, tick **Enable 3D Acceleration** |
| Storage → the VM's disk | tick **Solid-state Drive** (if the laptop has an SSD) |

### On the laptop (host)

- Keep it **plugged in**; set Windows power mode to **Best performance**.
- Close Chrome tabs, Teams, games and other heavy apps.
- A **green turtle** icon in the VM window's status bar means Windows Hyper-V is
  slowing VirtualBox down. Fix (Windows, admin PowerShell, then restart):
  `bcdedit /set hypervisorlaunchtype off`, and turn off *Core isolation → Memory
  integrity* in Windows Security.

### Inside the VM

```bash
gsettings set org.gnome.desktop.interface enable-animations false   # snappier desktop
sudo sysctl vm.swappiness=10                                         # use swap less (until reboot)
```

To keep the swap setting after reboots:

```bash
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-queneth.conf
```

## If something goes wrong

| Problem | Fix |
| --- | --- |
| Page won't open / "connection refused" | `vm/status.sh`. If something is down: `vm/start.sh --prod` (it starts only what's down). |
| `Port 8000 (or 3000) is taken` | `vm/stop.sh`, then `vm/start.sh --prod`. |
| Everything is slow | Check `vm/status.sh` → *Memory available*. Close apps, then see "Make the VM faster". |
| First page load is slow | Normal right after starting; open the main pages once before presenting. |
| Can't sign in | Use the exact accounts above and `Queneth#2026`. After 10 tries in a minute, wait one minute (login protection). |
| "Please sign in to continue" in a form | Your session expired. Sign in again; what you typed in the form stays. |
| Wrong PIN at checkout | The PIN is `123456`. |
| Store has test orders / messy data | `vm/reset.sh` |
| A service crashed | `vm/status.sh` says which; read `logs/api.log` or `logs/web.log`; `vm/start.sh --prod`. |
| Browser shows `401 Unauthorized` for `/api/v1/me` while signed out | Expected: it's the "am I signed in?" check. |
| Animations look toned down | Firefox in a VM reports reduced motion. `about:config` → `ui.prefersReducedMotion` = `0`. |
| You changed code or pulled from GitHub | `vm/stop.sh && vm/start.sh --prod` (rebuilds the storefront). |

## Getting the latest version from GitHub

```bash
cd ~/Queneth
git pull
vm/reset.sh
```

`vm/reset.sh` loads the store snapshot that came with the pull and rebuilds the storefront.

## Saving your own changes to the store

If you edited products in Seller Studio and want to keep them for next time (or
share them through GitHub):

```bash
cd ~/Queneth/backend && .venv/bin/python scripts/snapshot.py save
cd ~/Queneth && git add backend/snapshot && git commit -m "Update store snapshot" && git push
```

`vm/reset.sh` always goes back to the last saved snapshot.
