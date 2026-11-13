"""Recuperación de respaldos locales. No restaura nada sin confirmación explícita."""
import argparse
import json
from backups import create_snapshot,restore_snapshot

def main():
    parser=argparse.ArgumentParser(description='Respaldos locales Meta-Ride')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('backup',help='Crear una copia consistente, incluso con backend activo')
    commands.add_parser('info',help='Mostrar motor y conexión sin revelar contraseñas')
    restore=commands.add_parser('restore',help='Restaurar un respaldo local con backend detenido')
    restore.add_argument('name',help='Nombre .db que aparece en Administración / Respaldos')
    restore.add_argument('--confirm',required=True,help='RESTAURAR')
    args=parser.parse_args()
    try:
        if args.command=='info':
            from database import engine
            result={'engine':engine.dialect.name,'database':engine.url.database,'host':engine.url.host,'port':engine.url.port,'user':engine.url.username}
        else:result={'backup':create_snapshot().name} if args.command=='backup' else restore_snapshot(args.name,args.confirm)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as error:parser.exit(1,f'No se aplicó la operación: {error}\n')
if __name__=='__main__':main()
