#if INT_MACRO != 2
#error
#endif

#ifndef FLAG_MACRO
#error
#endif

void setup() {
  char string[]=STRING_MACRO; // Will fail if the macro is not a string literal
}
void loop(){}
