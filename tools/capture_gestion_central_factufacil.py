from __future__ import annotations
import argparse,sys,tempfile
from pathlib import Path
from PIL import ImageGrab
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bc_gestion_central import build_service
from modulos.gestion_central.factufacil import FactuFacilSale,FactuFacilService
from modulos.gestion_central.ui import CentralPilotWindow

def main():
    parser=argparse.ArgumentParser();parser.add_argument("output",type=Path);args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bc-factufacil-") as directory:
        core=build_service(Path(directory));core.bootstrap_synthetic_pilot();sol=core.authenticate("sol.piloto","Piloto-Temporal-2026");ff=FactuFacilService(core)
        examples=[("Casa Central","S-101","PARA", "OD -1.25 Esf / -0.50 Cil\nOI -1.00 Esf\nDP 62 mm\nObservación completa sin truncar"),("Pilar","S-202","CARGA","Control sintético de receta"),("Casa Central","S-303","OBS","Cambio posterior sintético")]
        ids=[]
        for index,(branch,envelope,_,prescription) in enumerate(examples):
            sale=FactuFacilSale(branch,f"sale-{index}",f"Cliente Sintético {index+1}",f"RUC-{index+1}",f"B-{index+1:03d}","2099-04-12",f"CAJA-{index+1:02d}",envelope,prescription,({"description":"Armazón sintético","price":400000},{"description":"Cristales sintéticos","price":600000}),1000000,"EFECTIVO + TARJETA",900000,100000,f"Vendedora {index+1}");sale_id,_=ff.register(sol,sale);ids.append(sale_id)
        ff.start(sol,ids[1]);ff.mark_loaded(sol,ids[2],"Leti","FAC-303");ff.register(sol,FactuFacilSale("Casa Central","sale-2","Cliente Sintético 3","RUC-3","B-003","2099-04-12","CAJA-03","S-303","Receta corregida sintética",({"description":"Armazón sintético","price":400000},{"description":"Cristales sintéticos","price":600000}),1000000,"EFECTIVO + TARJETA",900000,100000,"Vendedora 3"))
        app=CentralPilotWindow(core,notifier=lambda *_:None);app.root.overrideredirect(True);app.root.geometry("1920x1080+0+0");app.root.attributes("-topmost",True);app.root.update();app.show_factufacil();app.factufacil_panel.tree.selection_set(ids[0]);app.factufacil_panel.tree.event_generate("<<TreeviewSelect>>");app.root.update_idletasks();app.root.lift();app.root.focus_force();app.root.update();x,y=app.root.winfo_rootx(),app.root.winfo_rooty();ImageGrab.grab((x,y,x+app.root.winfo_width(),y+app.root.winfo_height())).save(args.output);app.root.destroy()
        for handler in list(app.logger.handlers):handler.close();app.logger.removeHandler(handler)
    print(f"BC_FACTUFACIL_CAPTURE_OK {args.output} 1920x1080");return 0
if __name__=="__main__":raise SystemExit(main())
