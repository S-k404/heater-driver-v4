import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); print('SES', pcbnew.ImportSpecctraSES(b, sys.argv[2])); b.Save(sys.argv[3])
