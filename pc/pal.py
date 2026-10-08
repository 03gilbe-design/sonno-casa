import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
# palette da stampa: coerente, leggibile, daltonic-safe
BG='#ffffff'; INK='#111827'; SOFT='#6b7280'; GRID='#e5e7eb'
BLU='#1d4ed8'; VER='#047857'; ARA='#b45309'; ROS='#b91c1c'; LIL='#6d28d9'; CIA='#0e7490'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
  'axes.edgecolor':'#9ca3af','axes.labelcolor':INK,'text.color':INK,
  'xtick.color':SOFT,'ytick.color':SOFT,'axes.titlesize':11,
  'figure.facecolor':BG,'axes.facecolor':BG,'savefig.facecolor':BG})
def clean(ax,grid='y'):
    for s in ['top','right']: ax.spines[s].set_visible(False)
    ax.tick_params(length=0); ax.set_axisbelow(True)
    if grid: ax.grid(axis=grid,color=GRID,lw=.8)
def salva(f,n,dpi=200):
    f.savefig(f'fig/{n}.pdf',bbox_inches='tight',facecolor=BG)
    f.savefig(f'fig/{n}.png',dpi=dpi,bbox_inches='tight',facecolor=BG)
    plt.close(f)
