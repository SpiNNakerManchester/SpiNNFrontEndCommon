# Tips for writing C code for spinnaker

### Logging

An example log statement is:
log_info("total_sim_ticks = %d", simulation_ticks);

#### Levels
We support 4 levels of logging
- log_error(
- log_warning(
- log_info(
- log_debug(

By default log_debug is off and the other three on.

#### Format Specifiers
We support the following format specifiers
- %c 	character
- %d 	decimal (integer) number (base 10)
- %f 	float
- %F    double
- %i 	integer (base 10)
- %s 	a string of characters
- %u 	unsigned decimal (integer) number
- %x 	number in hexadecimal (base 16)
- %R    Fixed point number
- %% 	print a percent sign

#### Converting to log_mini_ statements

Due to the extremely limited space on spinnaker the log_ statements are automatically modified by the make files to log_mini calls.

The modified c files which are the ones actually compiled can be found in the modified_src directory next to the original src directory.

The modifications include.
1. Replacing the String text with a number and just the Format Specifiers
2. Replacing the float and double logging with hex logging
   - The use of float and double is not recommeneded on spinnaker
   - There is NO code in spinnaker that supports formating these types
   - Instead they are converted to int(s) and then formatted in dexadecimal
3. The use of %s is not recommeneded instead please included the string in the original text.

When the data is read off spinnaker the modifications are reversed.
1. The number is converted back to the String with the file name and line are added
3. The hex values are converted back into float and double values

##### Limitations
Due to this conversion there are a few limitations.
1. The text part of the log message must be a simple string not a function or constant.
2. The number of parameters must match the number of format specifiers.
3. Functions in the parameters should work in most case. 
   - A known exception is if there are strings in these functions
4. Using ybug you will get the converted format. So the number and not the String.
   - A work around is to temporily change the line of most interest to a log_mini_line.  
     - Look at a modified_src file for an example
     - %f and %F are not supported by log_mini_ and may give incorrect results
     - Using log_mini directly will increase your code size
     - Using log_mini directly the final output will not have the file name and number information.
     - Do not use just a number in the String part of the log_mini

##### fprintf
The direct use of fprintf is not recommended.
 
- We reserve the right to change its capability or even remove it completly. 

- There is a risk that lines printed using fprintf directly could confuse the convert back stage. 


