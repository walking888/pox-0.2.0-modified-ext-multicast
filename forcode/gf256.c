
#include "stdio.h"
#include "stdlib.h"
#include "gf256.h"

FIELD* mtab=NULL;
FIELD* dtab=NULL;

inline FIELD gfsub(FIELD x, FIELD y)
{
    return (FIELD) ((x) ^ (y));
}
inline FIELD gfadd(FIELD x, FIELD y)
{
    return (FIELD) ((x) ^ (y));
}
inline FIELD gfmul(FIELD x, FIELD y)
{
    return (FIELD) (mtab[(x)*256+(y)]);
}
inline FIELD gfdiv(FIELD x, FIELD y)
{
    return (FIELD) (dtab[(x)*256+(y)]);
}

int initMulDivTab(char* fileName)
{
	FILE* f;
	if((f=fopen(fileName,"rb"))==NULL)
		return FALSE;
	mtab=(FIELD*)malloc(sizeof(FIELD)*65536);
	dtab=(FIELD*)malloc(sizeof(FIELD)*65536);
	fread(mtab,65536L,1,f);
	fread(dtab,65536L,1,f);
	fclose(f);
	return TRUE;
}

void freeDivTab()
{
    free(mtab);
    free(dtab);
}
